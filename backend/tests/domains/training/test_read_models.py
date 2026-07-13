"""Today/schedule-window/block-status read model tests against block0 canon.

Block0's window is `start=2026-07-06, days=28` (`block0.json`), so day 1 is
2026-07-06 and day 28 is 2026-08-02 — every date-boundary test below is
anchored to those two literal dates. The render-helper unit tests exercise
`render_scheme`/`render_segment`/`render_rule`/`render_gate`/`checkin_rows`
directly against both synthetic fixtures (to hit branches block0 never
exercises, e.g. `AllPredicate`/`NotPredicate`/`rhr.delta_7d`) and the real
imported schedule (to prove the projection end to end).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.domains.training.adapters import SqliteTrainingRepository
from app.domains.training.application.compile import compile_schedule
from app.domains.training.application.imports import ImportFile, ImportRequest, import_artifacts
from app.domains.training.application.read_models import (
    TrainingLogUpdateRequest,
    _active_context,  # pyright: ignore[reportPrivateUsage]
    _cards_for_day,  # pyright: ignore[reportPrivateUsage]
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
    TrainingCaptureLog,
    TrainingCheckinLog,
    TrainingExerciseLog,
    TrainingRunActivitySummary,
    TrainingSetLog,
)
from tests._architecture import REPO_ROOT

BLOCK0 = REPO_ROOT / "docs" / "routine-pivot" / "block0"
_BLOCK0_FILENAMES = [
    "block0.json",
    "running_v3.json",
    "strength_v3.json",
    "support_v3.json",
    "registry.json",
    "exercise_library.json",
]


def _load(name: str) -> dict:
    return json.loads((BLOCK0 / name).read_text(encoding="utf-8"))


def _block0_files() -> list[ImportFile]:
    return [ImportFile(filename=name, content=_load(name)) for name in _BLOCK0_FILENAMES]


def _imported_repo() -> SqliteTrainingRepository:
    repo = SqliteTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block0_files()))
    assert result.activated is True
    return repo


def _card(response, occurrence_key: str):
    return next(c for c in response.cards if c.occurrence_key == occurrence_key)


def _run(run_id: str, *, distance_mi: float | None = None) -> TrainingRunActivitySummary:
    return TrainingRunActivitySummary(
        run_id=run_id, start_time_local="2026-07-06T07:00:00", distance_mi=distance_mi
    )


class _FakeRunActivityPort:
    """Test double for `RunActivityReadPort` — a fixed date -> runs mapping.

    Records every `runs_for_date` call (date args, in order) in `self.calls`
    so tests can assert on whether — not just what — the port was queried,
    e.g. proving `_cards_for_day` skips it entirely on a run-card-free day.
    """

    def __init__(self, runs_by_date: dict[str, list[TrainingRunActivitySummary]]) -> None:
        self._runs_by_date = runs_by_date
        self.calls: list[str] = []

    def runs_for_date(self, date: str) -> list[TrainingRunActivitySummary]:
        self.calls.append(date)
        return self._runs_by_date.get(date, [])


# ---------- get_training_today: day boundaries ----------


def test_today_at_window_start_returns_day_one_checkin_first_and_patched_segments():
    repo = _imported_repo()
    response = get_training_today(repo, date="2026-07-06")

    assert response.block_id == "block0.calibration"
    assert response.block_name == "block0.calibration"
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


def test_today_with_no_active_block_returns_empty_response():
    repo = SqliteTrainingRepository()
    response = get_training_today(repo, date="2026-07-06")

    assert response.block_id is None
    assert response.block_name is None
    assert response.day is None
    assert response.cards == []


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
        "Gate: dew point (°C) <= 22; strap.validity_pct >= 0.95."
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
    response = get_training_today(repo, date="2026-07-21")  # day 16

    lthr = _card(response, "running.v3:run.lthr_test:d16")
    assert lthr.variant_options == ["full", "treadmill", "alternate_strides"]
    assert lthr.rule_display == (
        "Alternate_strides if ev_lthr_test already completed; "
        "Treadmill if dew point (°C) > 22; "
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
    assert repo.card_log("2026-07-06", "running.v3:run.easy:d01") is None


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


def test_cards_for_day_skips_run_activity_port_when_day_has_no_run_cards():
    """`_cards_for_day` must not call `runs_for_date` on a day with zero
    `running.v3` cards — the port deserializes every tracked-run session for
    the date, so a run-card-free day should be a no-op against it. Block0's
    canon window schedules a running card every single day, so this drops
    day 1's `running.v3:run.easy` entry from the real compiled schedule
    before calling `_cards_for_day` directly, leaving its two non-run cards
    (`sup.daily`, `str.push_a`) intact — proving the gate keys off the day's
    run-card *count*, not an empty day.
    """
    repo = _imported_repo()
    context = _active_context(repo)
    assert context is not None
    _block, bundles, registry, library = context
    bundle_names = {bundle.id: bundle.name for bundle in bundles}
    schedule = compile_schedule(bundles)
    schedule_without_running = [
        entry for entry in schedule if not (entry.day == 1 and entry.bundle_id == "running.v3")
    ]
    port = _FakeRunActivityPort({"2026-07-06": [_run("r1", distance_mi=6.9)]})

    cards = _cards_for_day(
        schedule_without_running,
        1,
        date="2026-07-06",
        registry=registry,
        library=library,
        bundle_names=bundle_names,
        repo=repo,
        run_activity_port=port,
    )

    assert port.calls == []
    assert [c.bundle_id for c in cards] == ["support.v3", "strength.v3"]
    assert all(c.associated_activity is None and c.run_candidates == [] for c in cards)


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


def test_schedule_window_never_associates_a_run_even_when_today_would_auto_match():
    """`get_training_schedule_window` never accepts a `RunActivityReadPort` — its
    call path leaves `_cards_for_day`'s port parameter at its default, so a run
    card here always renders unassociated, unlike the identical day read through
    `get_training_today` with a port supplied (see the Task 8 association tests
    above, which auto-link this exact day/card/distance combination).
    """
    repo = _imported_repo()
    window = get_training_schedule_window(repo, start_date="2026-07-06", duration_days=1)

    easy = _card(window.days[0], "running.v3:run.easy:d01")
    assert easy.associated_activity is None
    assert easy.run_candidates == []


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

    expected_day = (date.today() - date(2026, 7, 6)).days + 1
    if 1 <= expected_day <= 28:
        assert status.current_day == expected_day
        assert status.burn_in == (expected_day <= 7)
    else:
        assert status.current_day is None
        assert status.burn_in is None


# ---------- upsert_training_log ----------


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
    assert len(repo.card_logs_for("2026-07-06")) == 1


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
    assert render_rule(rule) == (
        "Full if not (quad flag); otherwise full; missing data → default."
    )


# ---------- render_gate ----------


def test_render_gate_formats_estimand_and_quality_gate():
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
        "Measurement: LTHR (bpm). Gate: dew point (°C) <= 22; RHR delta (bpm) > 5."
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
