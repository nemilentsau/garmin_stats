"""Today/schedule-window/block-status reads against fixture artifact sets.

The calibration fixture window is `start=2026-07-06, days=28` (`block0.json`), so day 1 is
2026-07-06 and day 28 is 2026-08-02 — every date-boundary test below is
anchored to those two literal dates. The render-helper unit tests exercise
`render_scheme`/`render_segment`/`render_rule`/`render_gate`/`checkin_rows`
directly against both synthetic fixtures (to hit branches the calibration set never
exercises, e.g. `AllPredicate`/`NotPredicate`/`rhr.delta_7d`) and the real
imported schedule (to prove the projection end to end).
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from app.domains.training.adapters import SqliteTrainingRepository
from app.domains.training.application.imports import ImportFile, ImportRequest, import_artifacts
from app.domains.training.application.read_models import (
    TrainingLogUpdateRequest,
    checkin_rows,
    get_block_status,
    get_training_schedule_window,
    get_training_today,
    match_run_to_card,
    render_gate,
    render_rule,
    render_scheme,
    render_segment,
    upsert_training_log,
)
from app.domains.training.contracts import (
    AllPredicate,
    Cmp,
    ExercisePrescriptionSpec,
    GuardedClause,
    LoadSpec,
    MeasurementContract,
    NotPredicate,
    SegmentIntensity,
    SegmentSpec,
    SelectionRule,
    SignalRegistry,
    StoredBundle,
    TrainingCaptureLog,
    TrainingCardLog,
    TrainingCheckinLog,
    TrainingExerciseLog,
    TrainingMeasurementAssessment,
    TrainingRunActivitySummary,
    TrainingRunEvidence,
    TrainingSetLog,
    TrainingTodayCard,
)
from tests._architecture import REPO_ROOT
from tests.domains.training._authored_program import load_authored_artifact

CALIBRATION_FIXTURE = (
    REPO_ROOT / "backend" / "tests" / "fixtures" / "training" / "v3-calibration"
)
_BLOCK0_FILENAMES = [
    "block0.json",
    "running_v3.json",
    "strength_v3.json",
    "support_v3.json",
    "registry.json",
    "exercise_library.json",
]
_BLOCK1_FILENAMES = [
    "block1.json",
    "running_v3.json",
    "strength_v3.json",
    "support_v3.json",
    "registry.json",
    "exercise_library.json",
]


def _load(name: str) -> dict:
    return json.loads((CALIBRATION_FIXTURE / name).read_text(encoding="utf-8"))


def _block0_files() -> list[ImportFile]:
    return [ImportFile(filename=name, content=_load(name)) for name in _BLOCK0_FILENAMES]


def _block1_files() -> list[ImportFile]:
    return [
        ImportFile(
            filename=name,
            content=load_authored_artifact(name),
        )
        for name in _BLOCK1_FILENAMES
    ]


def _imported_repo(
    *,
    include_measurement_event: bool = True,
    schedule_start: str | None = None,
) -> SqliteTrainingRepository:
    repo = SqliteTrainingRepository()
    result = import_artifacts(
        repo,
        ImportRequest(files=_block0_files(), schedule_start=schedule_start),
    )
    assert result.activated is True
    return repo if include_measurement_event else _NoMeasurementEventTrainingRepository()


def _imported_block1_repo(*, schedule_start: str | None = None) -> SqliteTrainingRepository:
    repo = SqliteTrainingRepository()
    result = import_artifacts(
        repo,
        ImportRequest(files=_block1_files(), schedule_start=schedule_start),
    )
    assert result.activated is True
    return repo


def _card(response, occurrence_key: str):
    return next(c for c in response.cards if c.occurrence_key == occurrence_key)


def _run(
    run_id: str,
    *,
    session_date: str = "2026-07-06",
    distance_mi: float | None = None,
) -> TrainingRunActivitySummary:
    return TrainingRunActivitySummary(
        run_id=run_id,
        session_date=session_date,
        start_time_local=f"{session_date}T07:00:00",
        distance_mi=distance_mi,
    )


class _FakeRunActivityPort:
    """Test double for `RunActivityReadPort` — a fixed date -> runs mapping.

    Records every inclusive `runs_between` call in `self.calls` so tests can
    assert Today uses one single-date read and the schedule window uses one
    bulk read rather than querying once per rendered day.
    """

    def __init__(
        self,
        runs_by_date: dict[str, list[TrainingRunActivitySummary]],
        *,
        evidence_by_run: dict[str, TrainingRunEvidence] | None = None,
    ) -> None:
        self._runs_by_date = runs_by_date
        self._evidence_by_run = evidence_by_run or {}
        self.calls: list[tuple[str, str]] = []
        self.evidence_calls: list[str] = []

    def runs_between(self, start_date: str, end_date: str) -> list[TrainingRunActivitySummary]:
        self.calls.append((start_date, end_date))
        return [
            run
            for date, runs in self._runs_by_date.items()
            if start_date <= date <= end_date
            for run in runs
        ]

    def evidence_for_run(self, run_id: str) -> TrainingRunEvidence:
        self.evidence_calls.append(run_id)
        try:
            return self._evidence_by_run[run_id]
        except KeyError as exc:
            raise LookupError(run_id) from exc


class _FakeMeasurementAssessmentPort:
    def __init__(
        self,
        assessment: TrainingMeasurementAssessment | None = None,
    ) -> None:
        self.assessment = assessment
        self.calls: list[tuple[str, str, str | None]] = []

    def latest_for(
        self,
        *,
        run_id: str,
        occurrence_key: str,
        before: str | None = None,
    ) -> TrainingMeasurementAssessment | None:
        self.calls.append((run_id, occurrence_key, before))
        return self.assessment


class _MappedMeasurementAssessmentPort:
    def __init__(
        self,
        assessments: dict[tuple[str, str], TrainingMeasurementAssessment],
    ) -> None:
        self.assessments = assessments
        self.calls: list[tuple[str, str, str | None]] = []

    def latest_for(
        self,
        *,
        run_id: str,
        occurrence_key: str,
        before: str | None = None,
    ) -> TrainingMeasurementAssessment | None:
        self.calls.append((run_id, occurrence_key, before))
        return self.assessments.get((run_id, occurrence_key))


class _TemporalMeasurementAssessmentPort:
    def __init__(
        self,
        assessments: dict[
            tuple[str, str],
            list[tuple[str, TrainingMeasurementAssessment]],
        ],
    ) -> None:
        self.assessments = assessments
        self.calls: list[tuple[str, str, str | None]] = []

    def latest_for(
        self,
        *,
        run_id: str,
        occurrence_key: str,
        before: str | None = None,
    ) -> TrainingMeasurementAssessment | None:
        self.calls.append((run_id, occurrence_key, before))
        cutoff = before
        if before is not None and len(before) == 10:
            cutoff = (
                datetime.combine(date.fromisoformat(before), time.min)
                .astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z")
            )
        eligible = [
            (created_at, assessment)
            for created_at, assessment in self.assessments.get(
                (run_id, occurrence_key), []
            )
            if cutoff is None or created_at < cutoff
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda item: item[0])[1]


def _measurement_evidence(
    run_id: str = "measurement-run",
    *,
    session_date: str = "2026-07-17",
) -> TrainingRunEvidence:
    elapsed_s = list(range(3301))
    summary = _run(run_id, session_date=session_date, distance_mi=7.0).model_copy(
        update={"hr_source": "strap"}
    )
    return TrainingRunEvidence(
        summary=summary,
        elapsed_s=elapsed_s,
        distance_mi=[second * (4.2 / 1800) for second in elapsed_s],
        heart_rate_bpm=[160 for _ in elapsed_s],
        run_walk_spans=[],
        dew_point_c=20,
    )


class _NoWriteTrainingRepository(SqliteTrainingRepository):
    """Repository that turns an accidental read-path write into a test failure."""

    def upsert_card_log(self, log: TrainingCardLog) -> None:
        raise AssertionError(f"GET attempted to persist card log {log.id}")


class _NoMeasurementEventTrainingRepository(SqliteTrainingRepository):
    """Present a valid imported block without events to exercise fallback policy."""

    def active_block(self):
        stored = super().active_block()
        assert stored is not None
        artifact = dict(stored.artifact)
        artifact["measurement_events"] = []
        return stored.model_copy(update={"artifact": artifact})


class _LegacyStartTrainingRepository(SqliteTrainingRepository):
    """Simulate a pre-schedule_start row loaded from an existing database."""

    def active_block(self):
        stored = super().active_block()
        assert stored is not None
        return stored.model_copy(update={"schedule_start": None})


class _NamedBlockTrainingRepository(SqliteTrainingRepository):
    """Present an authored human name that cannot be inferred from the id."""

    def active_block(self):
        stored = super().active_block()
        assert stored is not None
        artifact = dict(stored.artifact)
        artifact["name"] = "Athlete Threshold Build"
        return stored.model_copy(update={"artifact": artifact})


class _SharedCardMeasurementTrainingRepository(SqliteTrainingRepository):
    """Read-only test overlay with two events sharing one card and backup day."""

    def active_block(self):
        stored = super().active_block()
        assert stored is not None
        artifact = deepcopy(stored.artifact)
        second = deepcopy(artifact["measurement_events"][0])
        second["id"] = "ev_lthr_secondary"
        second["on_all_missed"] = "flag"
        artifact["measurement_events"].append(second)
        return stored.model_copy(update={"artifact": artifact})

    def bundles_for(self, bundle_ids: str | list[str]) -> list[StoredBundle]:
        stored_bundles = super().bundles_for(bundle_ids)
        adjusted = []
        for stored in stored_bundles:
            if stored.id != "running.v3":
                adjusted.append(stored)
                continue
            artifact = deepcopy(stored.artifact)
            second_slot = deepcopy(
                next(assignment for assignment in artifact["assignments"] if assignment["day"] == 8)
            )
            second_slot["slot"] = "evening"
            artifact["assignments"].append(second_slot)
            adjusted.append(stored.model_copy(update={"artifact": artifact}))
        return adjusted


class _TransitioningSharedCardTrainingRepository(SqliteTrainingRepository):
    """Test overlay whose same-card events have independently evaluable first tries."""

    def active_block(self):
        stored = super().active_block()
        assert stored is not None
        artifact = deepcopy(stored.artifact)
        second = deepcopy(artifact["measurement_events"][0])
        second["id"] = "ev_lthr_secondary"
        second["scheduled_day"] = 2
        second["on_all_missed"] = "flag"
        artifact["measurement_events"].append(second)
        return stored.model_copy(update={"artifact": artifact})

    def bundles_for(self, bundle_ids: str | list[str]) -> list[StoredBundle]:
        stored_bundles = super().bundles_for(bundle_ids)
        adjusted = []
        for stored in stored_bundles:
            if stored.id != "running.v3":
                adjusted.append(stored)
                continue
            artifact = deepcopy(stored.artifact)
            scheduled = deepcopy(
                next(assignment for assignment in artifact["assignments"] if assignment["day"] == 1)
            )
            scheduled.update(day=2, slot="evening")
            backup = deepcopy(
                next(assignment for assignment in artifact["assignments"] if assignment["day"] == 8)
            )
            backup["slot"] = "evening"
            artifact["assignments"].extend([scheduled, backup])
            adjusted.append(stored.model_copy(update={"artifact": artifact}))
        return adjusted


class _TwoBackupMeasurementTrainingRepository(SqliteTrainingRepository):
    """Test overlay with a second authored backup opportunity on block day 15."""

    def active_block(self):
        stored = super().active_block()
        assert stored is not None
        artifact = deepcopy(stored.artifact)
        artifact["measurement_events"][0]["backup_days"] = [8, 15]
        return stored.model_copy(update={"artifact": artifact})


def _imported_shared_card_repo() -> _SharedCardMeasurementTrainingRepository:
    repo = _SharedCardMeasurementTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block1_files()))
    assert result.activated is True
    return repo


def _imported_transitioning_shared_card_repo() -> _TransitioningSharedCardTrainingRepository:
    repo = _TransitioningSharedCardTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block1_files()))
    assert result.activated is True
    return repo


def _imported_two_backup_repo() -> _TwoBackupMeasurementTrainingRepository:
    repo = _TwoBackupMeasurementTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block1_files()))
    assert result.activated is True
    return repo


# ---------- get_training_today: day boundaries ----------


def test_today_at_window_start_returns_day_one_checkin_first_and_patched_segments():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-06")

    assert response.block_id == "block0.calibration"
    assert response.block_name == "Calibration"
    assert response.block_days == 28
    assert response.schedule_start == "2026-07-06"
    assert response.day == 1
    assert [c.occurrence_key for c in response.cards] == [
        "support.v3:sup.daily:d01",
        "running.v3:run.easy:d01",
        "strength.v3:str.push_a:d01",
    ]

    daily = _card(response, "support.v3:sup.daily:d01")
    assert daily.rule_display is None
    assert daily.variant_options == []
    assert len(daily.checkin_rows) == 6
    assert daily.capture_rpe is False
    assert [s.detail for s in daily.segments_display] == ["2 min · RPE 1", "12 min · RPE 4"]

    easy = _card(response, "running.v3:run.easy:d01")
    assert easy.capture_rpe is True
    assert easy.checkin_rows == []
    assert [s.detail for s in easy.segments_display] == ["7 mi · Z1-Z2"]


def test_today_before_window_start_returns_no_cards_but_keeps_block_identity():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-05")

    assert response.day is None
    assert response.cards == []
    assert response.block_id == "block0.calibration"


def test_today_after_window_end_returns_no_cards():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-08-03")

    assert response.day is None
    assert response.cards == []
    assert response.block_id == "block0.calibration"


def test_today_at_window_end_boundary_returns_day_28_with_cards():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-08-02")

    assert response.day == 28
    assert len(response.cards) == 4


@pytest.mark.parametrize(
    ("requested_date", "expected_day"),
    [
        ("2026-08-02", None),
        ("2026-08-03", 1),
        ("2026-08-30", 28),
        ("2026-08-31", None),
    ],
)
def test_today_uses_import_selected_start_for_program_boundaries(
    requested_date,
    expected_day,
):
    repo = _imported_repo(schedule_start="2026-08-03")

    response = get_training_today(repo, date=requested_date)

    assert response.day == expected_day
    assert bool(response.cards) is (expected_day is not None)


def test_today_uses_authored_start_for_legacy_stored_block():
    repo = _LegacyStartTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block0_files()))
    assert result.activated is True

    response = get_training_today(repo, date="2026-07-06")

    assert response.day == 1


def test_today_with_no_active_block_returns_empty_response():
    repo = SqliteTrainingRepository()
    response = get_training_today(repo, date="2026-07-06")

    assert response.block_id is None
    assert response.block_name is None
    assert response.block_days is None
    assert response.schedule_start is None
    assert response.day is None
    assert response.cards == []


def test_today_exposes_authored_program_and_concise_bundle_names():
    repo = _imported_block1_repo()

    response = get_training_today(repo, date="2026-07-13")

    assert response.block_name == "Threshold Development"
    assert {card.bundle_name for card in response.cards} == {
        "Running",
        "Strength",
        "Support",
    }


def test_today_prefers_authored_program_name_over_internal_id():
    repo = _NamedBlockTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block0_files()))
    assert result.activated is True

    response = get_training_today(repo, date="2026-07-06")

    assert response.block_name == "Athlete Threshold Build"


# ---------- get_training_today: card projection details ----------


def test_today_multi_variant_strength_card_exposes_variant_options_and_rule_text():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-07")  # day 2

    lower_a = _card(response, "strength.v3:str.lower_a:d02")
    assert lower_a.variant_options == ["full", "reduced", "skip"]
    assert lower_a.rule_display == (
        "Skip if quad flag or glute flag or HRV (SWC units) < -1.5; "
        "Reduced if HRV (SWC units) < -0.75 or quad soreness >= 2; "
        "otherwise full; missing data → conservative."
    )


def test_today_bare_comparison_rule_renders_without_any_or_all_wrapper():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-06")  # day 1

    push_a = _card(response, "strength.v3:str.push_a:d01")
    assert push_a.rule_display == (
        "Skip if HRV (SWC units) < -2; Reduced if HRV (SWC units) < -1.25; "
        "otherwise full; missing data → conservative."
    )


def test_today_measurement_card_exposes_gate_display_and_two_variants():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-17")  # day 12

    lthr = _card(response, "running.v3:run.lthr_test:d12")
    assert lthr.key_session is True
    assert lthr.variant_options == ["full", "skip"]
    assert lthr.gate_display == (
        "Measurement: LTHR (bpm), heat-season conditions; threshold pace secondary. "
        "Gate: dew point (°F) <= 71.6; strap.validity_pct >= 0.95."
    )
    assert lthr.capture_rpe is True
    assert [s.label for s in lthr.segments_display] == [
        "warmup",
        "30 min max sustainable effort; LTHR = mean HR of final 20 min",
        "cooldown",
    ]
    assert lthr.segments_display[0].detail == "1.7 mi · 15 min · Z1-Z2"


def test_today_rule_uses_event_completed_signal_and_three_variants():
    repo = _imported_repo()
    evidence = _measurement_evidence()
    response = get_training_today(
        repo,
        date="2026-07-21",  # day 16
        run_activity_port=_FakeRunActivityPort(
            {"2026-07-17": [evidence.summary]},
            evidence_by_run={evidence.summary.run_id: evidence},
        ),
        measurement_assessment_port=_FakeMeasurementAssessmentPort(
            TrainingMeasurementAssessment(
                status="valid",
                rationale="Scheduled attempt was valid.",
                source_id="review-day-12",
            )
        ),
    )

    lthr = _card(response, "running.v3:run.lthr_test:d16")
    assert lthr.variant_options == ["full", "treadmill", "alternate_strides"]
    assert lthr.rule_display == (
        "Alternate_strides if ev_lthr_test already completed; "
        "Treadmill if dew point (°F) > 71.6; "
        "otherwise full; missing data → conservative."
    )


def test_today_strength_card_projects_exercises_with_scheme_name_and_log_sets():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-06")  # day 1

    push_a = _card(response, "strength.v3:str.push_a:d01")
    assert len(push_a.exercises_display) == 6
    bench = push_a.exercises_display[0]
    assert bench.exercise_id == "barbell_bench"
    assert bench.name == "Barbell Bench Press"
    assert bench.scheme == "4×5–8 @ RPE 8"
    assert bench.log_sets is True
    assert push_a.segments_display == []


def test_today_card_requires_effective_execution():
    repo = _imported_repo()
    card = _card(get_training_today(repo, date="2026-07-06"), "running.v3:run.easy:d01")
    payload = card.model_dump()
    del payload["execution"]

    with pytest.raises(ValidationError, match="execution"):
        TrainingTodayCard.model_validate(payload)


def test_today_card_rejects_status_that_disagrees_with_execution():
    repo = _imported_repo()
    card = _card(get_training_today(repo, date="2026-07-06"), "running.v3:run.easy:d01")
    payload = card.model_dump()
    payload["status"] = "completed"

    with pytest.raises(ValidationError, match="execution status must match legacy status"):
        TrainingTodayCard.model_validate(payload)


# ---------- get_training_today: last-logged load anchor (Task 0.3) ----------


def test_today_strength_exercise_surfaces_last_logged_anchor_from_prior_session():
    repo = _imported_repo()
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="strength.v3:str.push_a:d01",
        update=TrainingLogUpdateRequest(
            status="completed",
            capture=TrainingCaptureLog(
                set_logs=[
                    TrainingExerciseLog(
                        exercise_id="barbell_bench",
                        sets=[TrainingSetLog(set_index=1, weight=90, reps=8)],
                    )
                ]
            ),
        ),
    )

    # str.push_a recurs on day 8 (2026-07-13); its barbell_bench should now anchor
    # to the set logged on day 1.
    next_push_a = _card(get_training_today(repo, date="2026-07-13"), "strength.v3:str.push_a:d08")
    bench = next(e for e in next_push_a.exercises_display if e.exercise_id == "barbell_bench")
    assert bench.last is not None
    assert (bench.last.weight_kg, bench.last.reps, bench.last.date) == (90.0, 8, "2026-07-06")


def test_today_strength_exercise_has_no_last_logged_anchor_before_any_prior_session():
    repo = _imported_repo()
    push_a = _card(get_training_today(repo, date="2026-07-06"), "strength.v3:str.push_a:d01")
    bench = next(e for e in push_a.exercises_display if e.exercise_id == "barbell_bench")
    assert bench.last is None


# ---------- match_run_to_card: matching policy (Task 8) ----------


def test_match_run_to_card_detached_with_no_manual_link_returns_none():
    result = match_run_to_card(
        linked_run_id=None,
        run_link_detached=True,
        prescribed_distance_mi=7.0,
        runs_today=[_run("r1", distance_mi=7.0)],
        run_cards_today=1,
    )
    assert result is None


def test_match_run_to_card_manual_link_wins_even_when_detached_flag_is_also_set():
    """A manual `linked_run_id` takes precedence over `run_link_detached` and over
    distance-closeness: the prescribed distance (5.0) is closer to r1, but the
    manually linked r2 is still returned.
    """
    runs = [_run("r1", distance_mi=5.0), _run("r2", distance_mi=9.0)]
    result = match_run_to_card(
        linked_run_id="r2",
        run_link_detached=True,
        prescribed_distance_mi=5.0,
        runs_today=runs,
        run_cards_today=1,
    )
    assert result is not None
    assert result.run_id == "r2"
    assert result.link_source == "manual"


def test_match_run_to_card_stale_manual_link_returns_none():
    result = match_run_to_card(
        linked_run_id="ghost",
        run_link_detached=False,
        prescribed_distance_mi=7.0,
        runs_today=[_run("r1", distance_mi=7.0)],
        run_cards_today=1,
    )
    assert result is None


def test_match_run_to_card_auto_links_the_only_run_when_one_run_card_scheduled():
    result = match_run_to_card(
        linked_run_id=None,
        run_link_detached=False,
        prescribed_distance_mi=7.0,
        runs_today=[_run("r1", distance_mi=6.5)],
        run_cards_today=1,
    )
    assert result is not None
    assert result.run_id == "r1"
    assert result.link_source == "auto"


def test_match_run_to_card_auto_picks_run_closest_to_prescribed_distance():
    runs = [_run("near", distance_mi=6.5), _run("far", distance_mi=9.0)]
    result = match_run_to_card(
        linked_run_id=None,
        run_link_detached=False,
        prescribed_distance_mi=7.0,
        runs_today=runs,
        run_cards_today=1,
    )
    assert result is not None
    assert result.run_id == "near"


def test_match_run_to_card_auto_picks_longest_run_when_card_has_no_distance_prescription():
    runs = [
        _run("short", distance_mi=3.0),
        _run("long", distance_mi=9.0),
        _run("mid", distance_mi=5.0),
    ]
    result = match_run_to_card(
        linked_run_id=None,
        run_link_detached=False,
        prescribed_distance_mi=None,
        runs_today=runs,
        run_cards_today=1,
    )
    assert result is not None
    assert result.run_id == "long"


def test_match_run_to_card_returns_none_when_multiple_run_cards_scheduled():
    result = match_run_to_card(
        linked_run_id=None,
        run_link_detached=False,
        prescribed_distance_mi=7.0,
        runs_today=[_run("r1", distance_mi=7.0)],
        run_cards_today=2,
    )
    assert result is None


def test_match_run_to_card_returns_none_when_no_runs_available():
    result = match_run_to_card(
        linked_run_id=None,
        run_link_detached=False,
        prescribed_distance_mi=7.0,
        runs_today=[],
        run_cards_today=1,
    )
    assert result is None


# ---------- get_training_today: run association (Task 8) ----------


def test_today_run_card_auto_links_the_days_only_run():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})
    response = get_training_today(repo, date="2026-07-06", run_activity_port=port)

    easy = _card(response, "running.v3:run.easy:d01")
    assert easy.associated_activity is not None
    assert easy.associated_activity.run_id == "r1"
    assert easy.associated_activity.link_source == "auto"
    assert [r.run_id for r in easy.run_candidates] == ["r1"]
    assert easy.status == "completed"
    assert easy.execution.status == "completed"
    assert easy.execution.source == "tracked_run"
    assert easy.execution.run_id == "r1"
    assert port.calls == [("2026-07-06", "2026-07-06")]
    assert repo.card_log("2026-07-06", "running.v3:run.easy:d01") is None


def test_today_run_completion_does_not_modify_existing_pending_log():
    repo = _imported_repo()
    occurrence_key = "running.v3:run.easy:d01"
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key=occurrence_key,
        update=TrainingLogUpdateRequest(status="pending", notes="keep me"),
    )
    before = repo.card_log("2026-07-06", occurrence_key)
    assert before is not None
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})

    response = get_training_today(
        _NoWriteTrainingRepository(), date="2026-07-06", run_activity_port=port
    )

    easy = _card(response, occurrence_key)
    assert easy.execution.status == "completed"
    assert easy.execution.source == "tracked_run"
    assert _NoWriteTrainingRepository().card_log("2026-07-06", occurrence_key) == before


def test_today_non_run_cards_never_get_run_association_fields():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})
    response = get_training_today(repo, date="2026-07-06", run_activity_port=port)

    for occurrence_key in ("support.v3:sup.daily:d01", "strength.v3:str.push_a:d01"):
        card = _card(response, occurrence_key)
        assert card.associated_activity is None
        assert card.run_candidates == []


def test_today_run_card_manual_link_overrides_auto_distance_match():
    repo = _imported_repo()
    # run.easy prescribes 7 mi total; "closer" is the auto pick by distance,
    # but the manual link below must win regardless.
    port = _FakeRunActivityPort(
        {"2026-07-06": [_run("closer", distance_mi=6.9), _run("farther", distance_mi=3.0)]}
    )
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(linked_run_id="farther"),
        run_activity_port=port,
    )

    easy = _card(
        get_training_today(repo, date="2026-07-06", run_activity_port=port),
        "running.v3:run.easy:d01",
    )
    assert easy.associated_activity is not None
    assert easy.associated_activity.run_id == "farther"
    assert easy.associated_activity.link_source == "manual"


def test_today_run_card_stale_link_shows_no_association_but_keeps_candidates():
    repo = _imported_repo()
    valid_port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(linked_run_id="r1"),
        run_activity_port=valid_port,
    )
    # A later read sees a different set of runs for the date (e.g. a
    # re-ingest changed run ids) — the saved link is now stale.
    stale_port = _FakeRunActivityPort({"2026-07-06": [_run("r2", distance_mi=5.0)]})

    easy = _card(
        get_training_today(repo, date="2026-07-06", run_activity_port=stale_port),
        "running.v3:run.easy:d01",
    )
    assert easy.associated_activity is None
    assert [r.run_id for r in easy.run_candidates] == ["r2"]


def test_today_run_card_detached_shows_no_association_but_keeps_candidates():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(run_link_detached=True),
    )

    easy = _card(
        get_training_today(repo, date="2026-07-06", run_activity_port=port),
        "running.v3:run.easy:d01",
    )
    assert easy.associated_activity is None
    assert [r.run_id for r in easy.run_candidates] == ["r1"]
    assert easy.status == "pending"
    assert easy.execution.status == "pending"
    assert easy.execution.source == "none"
    assert easy.execution.run_id is None


def test_today_without_run_activity_port_leaves_run_cards_unassociated():
    repo = _imported_repo()
    easy = _card(get_training_today(repo, date="2026-07-06"), "running.v3:run.easy:d01")
    assert easy.associated_activity is None
    assert easy.run_candidates == []


@pytest.mark.parametrize(
    ("assessment_status", "expected_status", "eligible", "retry"),
    [
        (None, "awaiting_review", False, False),
        ("valid", "valid", True, False),
        ("provisional", "provisional", False, True),
        ("failed", "failed", False, True),
    ],
)
def test_today_measurement_combines_objective_evidence_with_exact_assessment(
    assessment_status: str | None,
    expected_status: str,
    eligible: bool,
    retry: bool,
):
    repo = _imported_repo()
    evidence = _measurement_evidence()
    run_port = _FakeRunActivityPort(
        {"2026-07-17": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment = (
        None
        if assessment_status is None
        else TrainingMeasurementAssessment(
            status=assessment_status,  # type: ignore[arg-type]
            rationale="Reviewed this exact scheduled attempt.",
            source_id="review-17",
        )
    )
    assessment_port = _FakeMeasurementAssessmentPort(assessment)

    response = get_training_today(
        repo,
        date="2026-07-17",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    card = _card(response, "running.v3:run.lthr_test:d12")
    assert card.execution.status == "completed"
    assert card.measurement is not None
    assert card.measurement.status == expected_status
    assert card.measurement.estimator_eligible is eligible
    assert card.measurement.retry_required is retry
    assert card.measurement.observations.final20_hr_bpm == 160
    assert card.measurement.rationale == (assessment.rationale if assessment else None)
    assert card.measurement.assessment_source_id == (assessment.source_id if assessment else None)
    assert run_port.evidence_calls == ["measurement-run"]
    assert assessment_port.calls == [
        ("measurement-run", "running.v3:run.lthr_test:d12", None)
    ]


def test_today_measurement_without_evidence_stays_completed_and_awaiting_review():
    repo = _imported_repo()
    summary = _run("missing-evidence", session_date="2026-07-17", distance_mi=7.0).model_copy(
        update={"hr_source": "strap"}
    )
    run_port = _FakeRunActivityPort({"2026-07-17": [summary]})
    assessment_port = _FakeMeasurementAssessmentPort()

    response = get_training_today(
        repo,
        date="2026-07-17",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    card = _card(response, "running.v3:run.lthr_test:d12")
    assert card.execution.status == "completed"
    assert card.execution.run_id == "missing-evidence"
    assert card.associated_activity is not None
    assert card.measurement is not None
    assert card.measurement.status == "awaiting_review"
    assert card.measurement.run_id == "missing-evidence"
    assert card.measurement.observations.final20_hr_bpm is None
    assert card.measurement.observations.threshold_pace_min_per_mi is None
    assert card.measurement.observations.strap_validity_pct is None
    assert [gate.result for gate in card.measurement.gates] == ["unknown", "unknown"]
    assert run_port.evidence_calls == ["missing-evidence"]


def test_today_missing_evidence_cannot_be_upgraded_by_valid_assessment():
    repo = _imported_repo()
    summary = _run("missing-evidence", session_date="2026-07-17", distance_mi=7.0).model_copy(
        update={"hr_source": "strap"}
    )
    run_port = _FakeRunActivityPort({"2026-07-17": [summary]})
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="A prior review called this attempt valid.",
            source_id="review-stale-without-series",
        )
    )

    response = get_training_today(
        repo,
        date="2026-07-17",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    card = _card(response, "running.v3:run.lthr_test:d12")
    assert card.execution.status == "completed"
    assert card.measurement is not None
    assert card.measurement.status == "awaiting_review"
    assert card.measurement.estimator_eligible is False
    assert card.measurement.retry_required is False
    assert card.measurement.rationale is None
    assert card.measurement.assessment_source_id is None
    assert assessment_port.calls == []


def test_today_ordinary_run_has_no_measurement_or_evidence_lookup():
    repo = _imported_repo()
    run_port = _FakeRunActivityPort({"2026-07-06": [_run("ordinary-run", distance_mi=7.0)]})
    assessment_port = _FakeMeasurementAssessmentPort()

    response = get_training_today(
        repo,
        date="2026-07-06",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    card = _card(response, "running.v3:run.easy:d01")
    assert card.execution.status == "completed"
    assert card.measurement is None
    assert run_port.evidence_calls == []
    assert assessment_port.calls == []


def test_today_measurement_without_matching_block_event_is_not_retry_required():
    repo = _imported_repo(include_measurement_event=False)
    evidence = _measurement_evidence()
    run_port = _FakeRunActivityPort(
        {"2026-07-17": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="provisional",
            rationale="Useful but optional attempt.",
            source_id="review-optional",
        )
    )

    response = get_training_today(
        repo,
        date="2026-07-17",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    card = _card(response, "running.v3:run.lthr_test:d12")
    assert card.measurement is not None
    assert card.measurement.status == "provisional"
    assert card.measurement.retry_required is False


# ---------- get_training_schedule_window ----------


def test_schedule_window_with_no_active_block_returns_empty_days():
    repo = SqliteTrainingRepository()
    window = get_training_schedule_window(repo, start_date="2026-07-06", duration_days=5)

    assert window.start_date == "2026-07-06"
    assert window.end_date == "2026-07-10"
    assert window.days == []


def test_schedule_window_spans_in_window_days_with_cards():
    repo = _imported_repo()
    window = get_training_schedule_window(repo, start_date="2026-07-06", duration_days=3)

    assert [d.day for d in window.days] == [1, 2, 3]
    assert [len(d.cards) for d in window.days] == [3, 4, 3]


def test_schedule_window_includes_out_of_window_day_with_empty_cards():
    repo = _imported_repo()
    window = get_training_schedule_window(repo, start_date="2026-07-05", duration_days=2)

    assert window.days[0].day == 0
    assert window.days[0].cards == []
    assert window.days[1].day == 1
    assert len(window.days[1].cards) == 3


def test_schedule_window_never_surfaces_a_last_logged_anchor():
    """The planning window is read-only and never loads prior-log history (unlike Today)."""
    repo = _imported_repo()
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="strength.v3:str.push_a:d01",
        update=TrainingLogUpdateRequest(
            status="completed",
            capture=TrainingCaptureLog(
                set_logs=[
                    TrainingExerciseLog(
                        exercise_id="barbell_bench",
                        sets=[TrainingSetLog(set_index=1, weight=90, reps=8)],
                    )
                ]
            ),
        ),
    )

    window = get_training_schedule_window(repo, start_date="2026-07-13", duration_days=1)
    push_a = _card(window.days[0], "strength.v3:str.push_a:d08")
    bench = next(e for e in push_a.exercises_display if e.exercise_id == "barbell_bench")
    assert bench.last is None


def test_schedule_window_bulk_loads_once_and_associates_runs_on_their_session_dates():
    repo = _imported_repo()
    port = _FakeRunActivityPort(
        {
            "2026-07-06": [_run("day-1", distance_mi=6.9)],
            "2026-07-07": [_run("day-2", session_date="2026-07-07", distance_mi=4.0)],
        }
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-06",
        duration_days=2,
        run_activity_port=port,
        as_of_date="2026-07-07",
    )

    day_1_run = next(card for card in window.days[0].cards if card.bundle_id == "running.v3")
    day_2_run = next(card for card in window.days[1].cards if card.bundle_id == "running.v3")
    assert port.calls == [("2026-07-06", "2026-07-07")]
    assert day_1_run.associated_activity is not None
    assert day_1_run.associated_activity.run_id == "day-1"
    assert day_1_run.execution.status == "completed"
    assert day_2_run.associated_activity is not None
    assert day_2_run.associated_activity.run_id == "day-2"
    assert day_2_run.execution.status == "completed"


def test_schedule_window_projects_measurement_with_both_read_ports():
    repo = _imported_repo()
    evidence = _measurement_evidence()
    run_port = _FakeRunActivityPort(
        {"2026-07-17": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Protocol met.",
            source_id="review-window",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-17",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-16",
    )

    card = _card(window.days[0], "running.v3:run.lthr_test:d12")
    assert card.measurement is not None
    assert card.measurement.status == "valid"
    assert run_port.calls == [("2026-07-17", "2026-07-17")]
    assert run_port.evidence_calls == ["measurement-run"]
    assert assessment_port.calls == [
        ("measurement-run", "running.v3:run.lthr_test:d12", None)
    ]


def test_schedule_window_uses_distinct_as_of_and_display_assessment_snapshots():
    repo = _imported_block1_repo()
    evidence = _measurement_evidence(session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="One request must see one assessment snapshot.",
            source_id="review-snapshot",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-13",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-13",
    )

    card = _card(window.days[0], "running.v3:run.lthr_test:d01")
    assert card.measurement is not None
    assert card.measurement.status == "valid"
    assert run_port.calls == [("2026-07-13", "2026-07-13")]
    assert run_port.evidence_calls == ["measurement-run"]
    assert assessment_port.calls == [
        ("measurement-run", "running.v3:run.lthr_test:d01", "2026-07-14"),
        ("measurement-run", "running.v3:run.lthr_test:d01", None),
    ]


def test_schedule_and_measurement_horizons_use_import_selected_start():
    repo = _imported_block1_repo(schedule_start="2026-08-03")
    evidence = _measurement_evidence(session_date="2026-08-03")
    run_port = _FakeRunActivityPort(
        {"2026-08-03": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Runtime Day 1 protocol met.",
            source_id="review-runtime-start",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-08-03",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-08-03",
    )

    assert window.days[0].day == 1
    card = _card(window.days[0], "running.v3:run.lthr_test:d01")
    assert card.measurement is not None
    assert card.measurement.status == "valid"
    assert run_port.calls == [("2026-08-03", "2026-08-03")]
    assert assessment_port.calls == [
        ("measurement-run", "running.v3:run.lthr_test:d01", "2026-08-04"),
        ("measurement-run", "running.v3:run.lthr_test:d01", None),
    ]


def test_schedule_window_caches_missing_evidence_for_visible_elapsed_attempt():
    repo = _imported_block1_repo()
    summary = _run("missing-evidence", session_date="2026-07-13", distance_mi=7.0)
    run_port = _FakeRunActivityPort({"2026-07-13": [summary]})
    assessment_port = _FakeMeasurementAssessmentPort()

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-13",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-13",
    )

    card = _card(window.days[0], "running.v3:run.lthr_test:d01")
    assert card.measurement is not None
    assert run_port.evidence_calls == ["missing-evidence"]
    assert assessment_port.calls == []


def test_schedule_window_caches_missing_assessment_for_visible_elapsed_attempt():
    repo = _imported_block1_repo()
    evidence = _measurement_evidence(session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort()

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-13",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-13",
    )

    card = _card(window.days[0], "running.v3:run.lthr_test:d01")
    assert card.measurement is not None
    assert card.measurement.status == "awaiting_review"
    assert run_port.evidence_calls == ["measurement-run"]
    assert assessment_port.calls == [
        ("measurement-run", "running.v3:run.lthr_test:d01", "2026-07-14"),
        ("measurement-run", "running.v3:run.lthr_test:d01", None),
    ]


# ---------- authored measurement backup overlay ----------


def test_today_marks_the_original_measurement_attempt_as_scheduled():
    repo = _imported_block1_repo()

    response = get_training_today(repo, date="2026-07-13")

    card = _card(response, "running.v3:run.lthr_test:d01")
    assert card.measurement_event_id == "ev_lthr_test"
    assert card.measurement_attempt == "scheduled"


def test_today_activates_backup_in_running_slot_and_preserves_support_cards():
    repo = _imported_block1_repo()
    run_port = _FakeRunActivityPort({})

    response = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=_FakeMeasurementAssessmentPort(),
    )

    running = [card for card in response.cards if card.bundle_id == "running.v3"]
    assert [
        (card.card.id, card.measurement_event_id, card.measurement_attempt) for card in running
    ] == [("run.lthr_test", "ev_lthr_test", "backup")]
    assert any(card.card.id == "sup.daily" for card in response.cards)
    assert any(card.card.id == "str.pull_a" for card in response.cards)
    assert run_port.calls == [("2026-07-13", "2026-07-20")]


def test_today_valid_prior_attempt_keeps_authored_tempo_on_backup_day():
    repo = _imported_block1_repo()
    evidence = _measurement_evidence(session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Protocol met.",
            source_id="review-day-1",
        )
    )

    response = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    running = [card for card in response.cards if card.bundle_id == "running.v3"]
    assert [card.card.id for card in running] == ["run.tempo"]
    assert running[0].measurement_event_id is None
    assert running[0].measurement_attempt is None
    assert run_port.calls == [("2026-07-13", "2026-07-20")]
    assert run_port.evidence_calls == ["measurement-run"]


def test_schedule_window_evaluates_attempt_before_visible_window_with_one_bulk_read():
    repo = _imported_block1_repo()
    evidence = _measurement_evidence(session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Protocol met.",
            source_id="review-before-window",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    running = [card for card in window.days[0].cards if card.bundle_id == "running.v3"]
    assert [card.card.id for card in running] == ["run.tempo"]
    assert run_port.calls == [("2026-07-13", "2026-07-20")]
    assert run_port.evidence_calls == ["measurement-run"]


def test_schedule_window_missing_evidence_keeps_attempt_non_valid_and_activates_backup():
    repo = _imported_block1_repo()
    summary = _run("missing-series", session_date="2026-07-13", distance_mi=7.0)
    run_port = _FakeRunActivityPort({"2026-07-13": [summary]})
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Cannot override absent objective evidence.",
            source_id="review-without-series",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    running = [card for card in window.days[0].cards if card.bundle_id == "running.v3"]
    assert [(card.card.id, card.measurement_attempt) for card in running] == [
        ("run.lthr_test", "backup")
    ]
    assert run_port.calls == [("2026-07-13", "2026-07-20")]
    assert run_port.evidence_calls == ["missing-series"]
    assert assessment_port.calls == []


def test_schedule_window_empty_series_cannot_become_valid_or_suppress_backup():
    repo = _imported_block1_repo()
    summary = _run("empty-series", session_date="2026-07-13", distance_mi=7.0)
    evidence = TrainingRunEvidence(
        summary=summary,
        elapsed_s=[],
        distance_mi=[],
        heart_rate_bpm=[],
        run_walk_spans=[],
    )
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [summary]},
        evidence_by_run={summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="The empty series must not qualify.",
            source_id="review-empty-series",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    running = [card for card in window.days[0].cards if card.bundle_id == "running.v3"]
    assert [(card.card.id, card.measurement_attempt) for card in running] == [
        ("run.lthr_test", "backup")
    ]
    assert assessment_port.calls == []


def test_shared_card_backup_slots_keep_distinct_event_keys_and_attempt_state():
    repo = _imported_shared_card_repo()
    scheduled = get_training_today(repo, date="2026-07-13")
    scheduled_run = next(card for card in scheduled.cards if card.bundle_id == "running.v3")
    assert scheduled_run.measurement_event_id is None
    assert scheduled_run.measurement_attempt is None

    first_evidence = _measurement_evidence("backup-one", session_date="2026-07-20")
    second_evidence = _measurement_evidence("backup-two", session_date="2026-07-20")
    run_port = _FakeRunActivityPort(
        {"2026-07-20": [first_evidence.summary, second_evidence.summary]},
        evidence_by_run={
            first_evidence.summary.run_id: first_evidence,
            second_evidence.summary.run_id: second_evidence,
        },
    )
    displayed = get_training_today(repo, date="2026-07-20", run_activity_port=run_port)
    backups = [card for card in displayed.cards if card.measurement_attempt == "backup"]
    assert [card.measurement_event_id for card in backups] == [
        "ev_lthr_test",
        "ev_lthr_secondary",
    ]
    assert len({card.occurrence_key for card in backups}) == 2
    assert all(":event:" in card.occurrence_key for card in backups)

    first_key, second_key = (card.occurrence_key for card in backups)
    assessment_port = _MappedMeasurementAssessmentPort(
        {
            ("backup-one", first_key): TrainingMeasurementAssessment(
                status="valid",
                rationale="Primary event valid.",
                source_id="review-primary",
            ),
            ("backup-two", second_key): TrainingMeasurementAssessment(
                status="failed",
                rationale="Secondary event failed.",
                source_id="review-secondary",
            ),
        }
    )
    upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=first_key,
        update=TrainingLogUpdateRequest(linked_run_id="backup-one"),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=second_key,
        update=TrainingLogUpdateRequest(linked_run_id="backup-two"),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    run_port.evidence_calls.clear()
    assessment_port.calls.clear()
    visible = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-20",
    )

    visible_backups = [
        card for card in visible.days[0].cards if card.measurement_attempt == "backup"
    ]
    statuses = [
        card.measurement.status
        for card in visible_backups
        if card.measurement is not None
    ]
    assert statuses == [
        "valid",
        "failed",
    ]
    assert run_port.evidence_calls == ["backup-one", "backup-two"]
    assert assessment_port.calls == [
        ("backup-one", first_key, "2026-07-21"),
        ("backup-two", second_key, "2026-07-21"),
        ("backup-one", first_key, None),
        ("backup-two", second_key, None),
    ]

    after_final = get_training_schedule_window(
        repo,
        start_date="2026-07-21",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-21",
    )

    assert [action.model_dump() for action in after_final.required_actions] == [
        {"event_id": "ev_lthr_secondary", "action": "flag"}
    ]


def test_backup_identity_survives_sibling_activation_becoming_valid():
    repo = _imported_transitioning_shared_card_repo()
    scheduled_evidence = _measurement_evidence("scheduled-primary", session_date="2026-07-13")
    secondary_evidence = _measurement_evidence("backup-secondary", session_date="2026-07-20")
    run_port = _FakeRunActivityPort(
        {
            "2026-07-13": [scheduled_evidence.summary],
            "2026-07-20": [secondary_evidence.summary],
        },
        evidence_by_run={
            scheduled_evidence.summary.run_id: scheduled_evidence,
            secondary_evidence.summary.run_id: secondary_evidence,
        },
    )
    secondary_key = "running.v3:run.lthr_test:d08:event:ev_lthr_secondary"
    assessment_port = _MappedMeasurementAssessmentPort(
        {
            ("backup-secondary", secondary_key): TrainingMeasurementAssessment(
                status="valid",
                rationale="Secondary backup is valid.",
                source_id="review-secondary-stable",
            )
        }
    )

    initially_active = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    initial_backups = [
        card for card in initially_active.cards if card.measurement_attempt == "backup"
    ]
    assert [card.occurrence_key for card in initial_backups] == [
        "running.v3:run.lthr_test:d08:event:ev_lthr_test",
        secondary_key,
    ]

    upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=secondary_key,
        update=TrainingLogUpdateRequest(
            linked_run_id="backup-secondary",
            notes="Keep this event-owned state.",
        ),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    assessment_port.assessments[("scheduled-primary", "running.v3:run.lthr_test:d01")] = (
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Primary scheduled attempt became valid.",
            source_id="review-primary-transition",
        )
    )

    after_sibling_valid = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    remaining = [
        card for card in after_sibling_valid.cards if card.measurement_attempt == "backup"
    ]
    assert len(remaining) == 1
    secondary = remaining[0]
    assert secondary.measurement_event_id == "ev_lthr_secondary"
    assert secondary.occurrence_key == secondary_key
    assert secondary.notes == "Keep this event-owned state."
    assert secondary.associated_activity is not None
    assert secondary.associated_activity.run_id == "backup-secondary"
    assert secondary.measurement is not None
    assert secondary.measurement.status == "valid"


def test_late_prior_assessment_keeps_logged_backup_projected_and_writable():
    repo = _imported_block1_repo()
    scheduled_evidence = _measurement_evidence("scheduled-day-1", session_date="2026-07-13")
    backup_evidence = _measurement_evidence("backup-day-8", session_date="2026-07-20")
    run_port = _FakeRunActivityPort(
        {
            "2026-07-13": [scheduled_evidence.summary],
            "2026-07-20": [backup_evidence.summary],
        },
        evidence_by_run={
            scheduled_evidence.summary.run_id: scheduled_evidence,
            backup_evidence.summary.run_id: backup_evidence,
        },
    )
    scheduled_key = "running.v3:run.lthr_test:d01"
    backup_key = "running.v3:run.lthr_test:d08:event:ev_lthr_test"
    backup_assessment = TrainingMeasurementAssessment(
        status="valid",
        rationale="The backup produced valid evidence.",
        source_id="review-backup",
    )
    assessment_port = _TemporalMeasurementAssessmentPort(
        {
            ("backup-day-8", backup_key): [
                ("2026-07-20T12:00:00Z", backup_assessment)
            ]
        }
    )

    initially_active = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    assert _card(initially_active, backup_key).measurement_attempt == "backup"
    upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=backup_key,
        update=TrainingLogUpdateRequest(
            linked_run_id="backup-day-8",
            notes="Completed on the authored backup day.",
        ),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    assessment_port.assessments[("scheduled-day-1", scheduled_key)] = [
        (
            "2026-07-22T12:00:00Z",
            TrainingMeasurementAssessment(
                status="valid",
                rationale="The original attempt was reviewed after the backup.",
                source_id="review-late-original",
            ),
        )
    ]
    historical = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    backup = _card(historical, backup_key)
    assert backup.notes == "Completed on the authored backup day."
    assert backup.associated_activity is not None
    assert backup.associated_activity.run_id == "backup-day-8"
    assert backup.measurement is not None
    assert backup.measurement.status == "valid"
    updated = upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=backup_key,
        update=TrainingLogUpdateRequest(notes="Still writable after the late review."),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    assert updated.notes == "Still writable after the late review."


_DAY_8_START_UTC = datetime.combine(date(2026, 7, 20), time.min).astimezone(UTC)


@pytest.mark.parametrize(
    ("assessment_created_at", "expected_card_id"),
    [
        (
            (_DAY_8_START_UTC - timedelta(seconds=1))
            .isoformat()
            .replace("+00:00", "Z"),
            "run.tempo",
        ),
        (
            _DAY_8_START_UTC.isoformat().replace("+00:00", "Z"),
            "run.lthr_test",
        ),
    ],
    ids=["before-backup-day", "on-backup-day"],
)
def test_backup_decision_uses_exclusive_backup_day_assessment_cutoff(
    assessment_created_at: str,
    expected_card_id: str,
):
    repo = _imported_block1_repo()
    evidence = _measurement_evidence("scheduled-day-1", session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _TemporalMeasurementAssessmentPort(
        {
            ("scheduled-day-1", "running.v3:run.lthr_test:d01"): [
                (
                    assessment_created_at,
                    TrainingMeasurementAssessment(
                        status="valid",
                        rationale="Assessment boundary case.",
                        source_id=f"review-{assessment_created_at}",
                    ),
                )
            ]
        }
    )

    response = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    running = [card for card in response.cards if card.bundle_id == "running.v3"]
    assert [card.card.id for card in running] == [expected_card_id]


def test_late_valid_suppresses_later_backup_and_current_extension_only():
    repo = _imported_two_backup_repo()
    evidence = _measurement_evidence("scheduled-day-1", session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _TemporalMeasurementAssessmentPort(
        {
            ("scheduled-day-1", "running.v3:run.lthr_test:d01"): [
                (
                    "2026-07-22T12:00:00Z",
                    TrainingMeasurementAssessment(
                        status="valid",
                        rationale="Valid after day 8 and before day 15.",
                        source_id="review-between-backups",
                    ),
                )
            ]
        }
    )

    future_visible = get_training_schedule_window(
        repo,
        start_date="2026-07-27",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-20",
    )
    assert [
        card.card.id
        for card in future_visible.days[0].cards
        if card.bundle_id == "running.v3"
    ] == ["run.tempo"]

    run_port.calls.clear()
    run_port.evidence_calls.clear()
    assessment_port.calls.clear()
    current = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=8,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-28",
    )

    day_8_run = next(
        card for card in current.days[0].cards if card.bundle_id == "running.v3"
    )
    day_15_run = next(
        card for card in current.days[-1].cards if card.bundle_id == "running.v3"
    )
    assert day_8_run.card.id == "run.lthr_test"
    assert day_8_run.measurement_attempt == "backup"
    assert day_15_run.card.id == "run.tempo"
    assert current.required_actions == []
    assert run_port.calls == [("2026-07-13", "2026-07-27")]
    assert run_port.evidence_calls == ["scheduled-day-1"]
    assert assessment_port.calls == [
        ("scheduled-day-1", "running.v3:run.lthr_test:d01", "2026-07-20"),
        ("scheduled-day-1", "running.v3:run.lthr_test:d01", "2026-07-27"),
        ("scheduled-day-1", "running.v3:run.lthr_test:d01", "2026-07-29"),
    ]
    assert len(assessment_port.calls) == len(set(assessment_port.calls))


def test_schedule_window_future_days_do_not_advance_required_actions():
    repo = _imported_block1_repo()
    run_port = _FakeRunActivityPort({})

    window = get_training_schedule_window(
        repo,
        start_date="2026-07-13",
        duration_days=9,
        run_activity_port=run_port,
        as_of_date="2026-07-13",
    )

    assert window.required_actions == []
    assert run_port.calls == [("2026-07-13", "2026-07-21")]


def test_future_visible_window_does_not_fetch_attempt_future_relative_to_as_of():
    repo = _imported_block1_repo()
    run_port = _FakeRunActivityPort({})

    get_training_schedule_window(
        repo,
        start_date="2026-07-21",
        duration_days=1,
        run_activity_port=run_port,
        as_of_date="2026-07-12",
    )

    assert run_port.calls == [("2026-07-21", "2026-07-21")]


def test_required_action_uses_as_of_strictly_after_final_backup_day():
    repo = _imported_block1_repo()

    on_final_day = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=1,
        as_of_date="2026-07-20",
    )
    after_final_day = get_training_schedule_window(
        repo,
        start_date="2026-07-20",
        duration_days=1,
        as_of_date="2026-07-21",
    )

    assert on_final_day.required_actions == []
    assert [action.model_dump() for action in after_final_day.required_actions] == [
        {"event_id": "ev_lthr_test", "action": "extend_block"}
    ]


def test_required_action_is_consistent_for_historical_and_future_windows():
    repo = _imported_block1_repo()

    historical = get_training_schedule_window(
        repo,
        start_date="2026-07-13",
        duration_days=1,
        as_of_date="2026-07-21",
    )
    future = get_training_schedule_window(
        repo,
        start_date="2026-08-01",
        duration_days=1,
        as_of_date="2026-07-21",
    )

    expected = [{"event_id": "ev_lthr_test", "action": "extend_block"}]
    assert [action.model_dump() for action in historical.required_actions] == expected
    assert [action.model_dump() for action in future.required_actions] == expected


def test_valid_backup_suppresses_required_action_after_final_day():
    repo = _imported_block1_repo()
    evidence = _measurement_evidence(session_date="2026-07-20")
    run_port = _FakeRunActivityPort(
        {"2026-07-20": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Backup attempt was valid.",
            source_id="review-valid-backup",
        )
    )

    window = get_training_schedule_window(
        repo,
        start_date="2026-08-01",
        duration_days=1,
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
        as_of_date="2026-07-21",
    )

    assert window.required_actions == []
    assert run_port.calls == [("2026-07-13", "2026-08-01")]
    assert run_port.evidence_calls == ["measurement-run"]
    assert assessment_port.calls == [
        (
            "measurement-run",
            "running.v3:run.lthr_test:d08:event:ev_lthr_test",
            "2026-07-22",
        )
    ]


# ---------- get_block_status ----------


def test_block_status_with_no_import_returns_none():
    repo = SqliteTrainingRepository()
    assert get_block_status(repo) is None


def test_block_status_reports_lint_report_and_dynamic_current_day():
    repo = _imported_repo()
    status = get_block_status(repo)

    assert status is not None
    assert status.block.id == "block0.calibration"
    assert status.lint_report.errors == []
    assert status.warning_acks == []
    assert status.activated_at
    assert status.schedule_start == "2026-07-06"

    expected_day = (date.today() - date(2026, 7, 6)).days + 1
    if 1 <= expected_day <= 28:
        assert status.current_day == expected_day
        assert status.burn_in == (expected_day <= 7)
    else:
        assert status.current_day is None
        assert status.burn_in is None


def test_block_status_current_day_uses_import_selected_start():
    runtime_today = date.today().isoformat()
    repo = _imported_repo(schedule_start=runtime_today)

    status = get_block_status(repo)

    assert status is not None
    assert status.schedule_start == runtime_today
    assert status.current_day == 1
    assert status.burn_in is True


# ---------- upsert_training_log ----------


def test_upsert_accepts_displayed_backup_status_and_notes():
    repo = _imported_block1_repo()
    run_port = _FakeRunActivityPort({})
    assessment_port = _FakeMeasurementAssessmentPort()
    displayed = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    backup = next(card for card in displayed.cards if card.measurement_attempt == "backup")

    saved = upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=backup.occurrence_key,
        update=TrainingLogUpdateRequest(status="completed", notes="Backup attempt completed."),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    assert saved.status == "completed"
    assert saved.notes == "Backup attempt completed."
    refreshed = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    projected = _card(refreshed, backup.occurrence_key)
    assert projected.status == "completed"
    assert projected.notes == "Backup attempt completed."


def test_upsert_accepts_manual_link_and_detach_for_displayed_backup():
    repo = _imported_block1_repo()
    run = _run("backup-run", session_date="2026-07-20", distance_mi=7.0)
    run_port = _FakeRunActivityPort({"2026-07-20": [run]})
    assessment_port = _FakeMeasurementAssessmentPort()
    displayed = get_training_today(
        repo,
        date="2026-07-20",
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    backup = next(card for card in displayed.cards if card.measurement_attempt == "backup")

    linked = upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=backup.occurrence_key,
        update=TrainingLogUpdateRequest(linked_run_id="backup-run"),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )
    detached = upsert_training_log(
        repo,
        date="2026-07-20",
        occurrence_key=backup.occurrence_key,
        update=TrainingLogUpdateRequest(linked_run_id=None, run_link_detached=True),
        run_activity_port=run_port,
        measurement_assessment_port=assessment_port,
    )

    assert linked.linked_run_id == "backup-run"
    assert detached.linked_run_id is None
    assert detached.run_link_detached is True


def test_upsert_rejects_inactive_backup_when_prior_attempt_is_valid():
    repo = _imported_block1_repo()
    evidence = _measurement_evidence(session_date="2026-07-13")
    run_port = _FakeRunActivityPort(
        {"2026-07-13": [evidence.summary]},
        evidence_by_run={evidence.summary.run_id: evidence},
    )
    assessment_port = _FakeMeasurementAssessmentPort(
        TrainingMeasurementAssessment(
            status="valid",
            rationale="Scheduled attempt was valid.",
            source_id="review-valid-scheduled",
        )
    )

    with pytest.raises(LookupError, match="no scheduled occurrence"):
        upsert_training_log(
            repo,
            date="2026-07-20",
            occurrence_key="running.v3:run.lthr_test:d08",
            update=TrainingLogUpdateRequest(notes="Must not save."),
            run_activity_port=run_port,
            measurement_assessment_port=assessment_port,
        )


def test_upsert_training_log_round_trips_through_today():
    repo = _imported_repo()
    capture = TrainingCaptureLog(checkin=TrainingCheckinLog(soreness={"quad": 1}))
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(status="completed", variant_taken="full", capture=capture),
    )

    daily = _card(get_training_today(repo, date="2026-07-06"), "support.v3:sup.daily:d01")
    assert daily.status == "completed"
    assert daily.variant_taken == "full"
    assert daily.capture is not None
    assert daily.capture.checkin is not None
    assert daily.capture.checkin.soreness == {"quad": 1}


def test_upsert_training_log_partial_update_preserves_unset_fields():
    repo = _imported_repo()
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(status="completed", variant_taken="full"),
    )

    second = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(notes="felt good"),
    )

    assert second.status == "completed"
    assert second.variant_taken == "full"
    assert second.notes == "felt good"


def test_upsert_training_log_is_idempotent_and_does_not_duplicate_rows():
    repo = _imported_repo()
    update = TrainingLogUpdateRequest(status="completed", variant_taken="full")

    first = upsert_training_log(
        repo, date="2026-07-06", occurrence_key="support.v3:sup.daily:d01", update=update
    )
    second = upsert_training_log(
        repo, date="2026-07-06", occurrence_key="support.v3:sup.daily:d01", update=update
    )

    assert first == second
    assert len(repo.card_logs_before("2026-07-07")) == 1


# ---------- upsert_training_log: occurrence validation (Fix 2) ----------


def test_upsert_training_log_rejects_unknown_occurrence_key_on_a_valid_day():
    repo = _imported_repo()
    with pytest.raises(LookupError):
        upsert_training_log(
            repo,
            date="2026-07-06",
            occurrence_key="support.v3:sup.daily:d99",
            update=TrainingLogUpdateRequest(status="completed"),
        )


def test_upsert_training_log_rejects_valid_key_on_a_date_outside_the_window():
    repo = _imported_repo()
    with pytest.raises(LookupError):
        upsert_training_log(
            repo,
            date="2026-07-05",  # one day before block0's window starts
            occurrence_key="support.v3:sup.daily:d01",
            update=TrainingLogUpdateRequest(status="completed"),
        )


def test_upsert_training_log_rejects_any_key_with_no_active_block():
    repo = SqliteTrainingRepository()
    with pytest.raises(LookupError):
        upsert_training_log(
            repo,
            date="2026-07-06",
            occurrence_key="support.v3:sup.daily:d01",
            update=TrainingLogUpdateRequest(status="completed"),
        )


# ---------- upsert_training_log: explicit-null-clears / absent-keeps (Fix 3) ----------


def test_upsert_training_log_status_only_update_keeps_notes_and_capture():
    repo = _imported_repo()
    capture = TrainingCaptureLog(checkin=TrainingCheckinLog(soreness={"quad": 1}))
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(notes="felt good", capture=capture),
    )

    second = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(status="completed"),
    )

    assert second.status == "completed"
    assert second.notes == "felt good"
    assert second.capture == capture


def test_upsert_training_log_explicit_null_notes_clears_stored_notes():
    repo = _imported_repo()
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(notes="felt good"),
    )

    cleared = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="support.v3:sup.daily:d01",
        update=TrainingLogUpdateRequest(notes=None),
    )

    assert "notes" in TrainingLogUpdateRequest(notes=None).model_fields_set
    assert cleared.notes is None


# ---------- upsert_training_log: run-link fields (Task 8) ----------


def test_upsert_training_log_links_run_id_when_valid_for_date():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})

    log = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(linked_run_id="r1"),
        run_activity_port=port,
    )

    assert log.linked_run_id == "r1"
    assert log.run_link_detached is False


def test_upsert_training_log_rejects_linked_run_id_not_among_the_dates_runs():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})

    with pytest.raises(ValueError):
        upsert_training_log(
            repo,
            date="2026-07-06",
            occurrence_key="running.v3:run.easy:d01",
            update=TrainingLogUpdateRequest(linked_run_id="ghost"),
            run_activity_port=port,
        )


def test_upsert_training_log_rejects_linked_run_id_when_no_port_supplied():
    """A missing `run_activity_port` is treated as "no runs for this date" —
    any non-null `linked_run_id` is rejected, never silently accepted.
    """
    repo = _imported_repo()

    with pytest.raises(ValueError):
        upsert_training_log(
            repo,
            date="2026-07-06",
            occurrence_key="running.v3:run.easy:d01",
            update=TrainingLogUpdateRequest(linked_run_id="r1"),
        )


def test_upsert_training_log_detaches_run_link():
    repo = _imported_repo()

    log = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(run_link_detached=True),
    )

    assert log.run_link_detached is True
    assert log.linked_run_id is None


def test_upsert_training_log_partial_update_preserves_linked_run_id_when_field_absent():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(linked_run_id="r1"),
        run_activity_port=port,
    )

    second = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(status="completed"),
    )

    assert second.linked_run_id == "r1"
    assert second.status == "completed"


def test_upsert_training_log_explicit_null_linked_run_id_clears_it():
    repo = _imported_repo()
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})
    upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(linked_run_id="r1"),
        run_activity_port=port,
    )

    cleared = upsert_training_log(
        repo,
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        update=TrainingLogUpdateRequest(linked_run_id=None),
    )

    assert cleared.linked_run_id is None


# ---------- render_scheme ----------


def test_render_scheme_prefers_pct_e1rm_over_rpe():
    exercise = ExercisePrescriptionSpec(
        exercise_id="pendulum_squat",
        targets=["quad"],
        sets=3,
        reps=(2, 3),
        load=LoadSpec(pct_e1rm=0.87, rpe=8),
        logging="set_rep_load",
    )
    assert render_scheme(exercise) == "3×2–3 @ 87% e1RM"


def test_render_scheme_uses_rpe_when_no_pct_e1rm():
    exercise = ExercisePrescriptionSpec(
        exercise_id="barbell_bench",
        targets=["upper_push"],
        sets=4,
        reps=(5, 8),
        load=LoadSpec(rpe=8),
        logging="set_rep_load",
    )
    assert render_scheme(exercise) == "4×5–8 @ RPE 8"


def test_render_scheme_uses_absolute_kg_as_last_resort():
    exercise = ExercisePrescriptionSpec(
        exercise_id="farmer_carry",
        targets=["grip_carry"],
        sets=3,
        reps=(1, 1),
        load=LoadSpec(absolute_kg=50),
        logging="set_rep_load",
    )
    assert render_scheme(exercise) == "3×1–1 @ 50 kg"


# ---------- render_segment ----------


def test_render_segment_joins_distance_and_zone():
    segment = SegmentSpec(label="easy", intensity=SegmentIntensity(zone="Z1-Z2"), distance_mi=7.0)
    assert render_segment(segment) == "7 mi · Z1-Z2"


def test_render_segment_joins_duration_and_rpe():
    segment = SegmentSpec(label="core", intensity=SegmentIntensity(rpe=4), duration_min=12)
    assert render_segment(segment) == "12 min · RPE 4"


def test_render_segment_uses_hr_range_when_no_zone_or_rpe():
    segment = SegmentSpec(label="tempo", intensity=SegmentIntensity(hr_range=(140, 150)))
    assert render_segment(segment) == "140–150 bpm"


# ---------- render_rule ----------


def test_render_rule_returns_none_for_empty_clauses():
    rule = SelectionRule(clauses=[], default="full", on_missing_signal="select_default")
    assert render_rule(rule) is None


def test_render_rule_all_predicate_uses_and_conjunction():
    rule = SelectionRule(
        clauses=[
            GuardedClause(
                when=AllPredicate(
                    all=[
                        Cmp(signal="sleep.score", op="<", value=50),
                        Cmp(signal="rhr.delta_7d", op=">", value=5),
                    ]
                ),
                select="reduced",
            )
        ],
        default="full",
        on_missing_signal="ask",
    )
    assert render_rule(rule) == (
        "Reduced if sleep score < 50 and RHR delta (bpm) > 5; otherwise full; missing data → ask."
    )


def test_render_rule_not_predicate_negates_signal():
    rule = SelectionRule(
        clauses=[
            GuardedClause(
                when=NotPredicate.model_validate(
                    {"not": Cmp(signal="flag.tissue.quad", op="==", value=True)}
                ),
                select="full",
            )
        ],
        default="full",
        on_missing_signal="select_default",
    )
    assert render_rule(rule) == ("Full if not (quad flag); otherwise full; missing data → default.")


# ---------- render_gate ----------


def test_render_gate_formats_estimand_and_converts_dew_point_to_fahrenheit():
    contract = MeasurementContract(
        kind="measurement",
        estimand="LTHR (bpm)",
        quality_gate=[
            Cmp(signal="env.dew_point", op="<=", value=22),
            Cmp(signal="rhr.delta_7d", op=">", value=5),
        ],
        on_fail="retry_backup",
    )
    assert render_gate(contract) == (
        "Measurement: LTHR (bpm). Gate: dew point (°F) <= 71.6; RHR delta (bpm) > 5."
    )


# ---------- checkin_rows ----------


def test_checkin_rows_returns_six_tissues_in_registry_order_with_slash_labels():
    repo = _imported_repo()
    registry = repo.registry()
    assert registry is not None

    rows = checkin_rows(SignalRegistry.model_validate(registry.artifact))

    assert [r.tissue for r in rows] == [
        "quad",
        "glute",
        "hamstring",
        "calf_achilles",
        "soleus",
        "tibialis_foot",
    ]
    assert next(r for r in rows if r.tissue == "tibialis_foot").label == "tibialis / foot"
    assert next(r for r in rows if r.tissue == "quad").label == "quad"
