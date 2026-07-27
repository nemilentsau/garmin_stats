"""Integration tests for bounded, refreshable coach evidence workspaces."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.coach.application.memory import render_run_journal
from app.domains.coach.contracts import (
    ArtifactRef,
    BriefVersion,
    CoachMeasurementAssessment,
    CoachMessage,
    CoachReview,
    HistoricalEvidenceUse,
    JournalEntry,
    PlotObservation,
    RunJournalSummary,
)
from app.domains.garmin_analytics.contracts import (
    DashboardOverviewResponse,
    EvidenceRow,
    MeaningfulChange,
    RunChartSeries,
    RunDetailResponse,
    RunDisplayStats,
    RunListItem,
    RunSeriesResponse,
)
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    RunningActivitySeries,
    RunningActivitySession,
)
from app.domains.journal.contracts import DailyCheckIn, Note
from app.domains.training.contracts import (
    BlockWindow,
    TrainingScheduleWindow,
    TrainingTodayResponse,
    V3Block,
)

NOW = "2026-07-12T12:00:00Z"


class FakeCoachRepository:
    def __init__(self) -> None:
        self.journal: list[JournalEntry] = []
        self.brief: BriefVersion | None = None
        self.reviews: dict[str, CoachReview] = {}

    def list_journal(
        self,
        *,
        limit: int | None = None,
        policy_version: int | None = None,
    ) -> list[JournalEntry]:
        entries = self.journal
        if policy_version is not None:
            entries = [
                entry for entry in entries if entry.policy_version == policy_version
            ]
        return entries if limit is None else entries[-limit:]

    def current_brief(
        self, *, policy_version: int | None = None
    ) -> BriefVersion | None:
        if self.brief is None:
            return None
        if policy_version is not None and self.brief.policy_version != policy_version:
            return None
        return self.brief

    def review(self, review_id: str) -> CoachReview | None:
        return self.reviews.get(review_id)


class FakeCoachGateway:
    def __init__(self, run_count: int = 22) -> None:
        first = date(2026, 6, 1)
        self.runs = [
            RunListItem(
                id=f"run-{index:02d}",
                session_date=(first + timedelta(days=index)).isoformat(),
                start_time_local=f"{(first + timedelta(days=index)).isoformat()}T06:00:00",
                activity_name=f"Run {index}",
                distance_mi=5 + index / 10,
                timer_time_s=2400,
                pace_min_per_mi=8.0,
                avg_heart_rate_bpm=140,
                hr_source="wrist",
                training_load=250.0,
                aerobic_training_effect=3.5,
            )
            for index in range(run_count)
        ]
        self.recent_runs_calls: list[int] = []
        self.overview: DashboardOverviewResponse | None = DashboardOverviewResponse(
            date="2026-07-12",
            change=MeaningfulChange(delta7_z=0.3, is_meaningful=True, direction="improving"),
            evidence=[
                EvidenceRow(
                    metric="hrv",
                    label="HRV",
                    tab_href="/hrv",
                    source_type="native",
                    latest_value=58,
                    unit="ms",
                    coverage_ok=True,
                )
            ],
        )
        self.metrics = [
            DailyMetric(
                date="2026-07-12",
                heart_rate=DailyHeartRateStats(),
                stress=DailyMetricStats(),
                body_battery=DailyBodyBatteryStats(),
                spo2=DailyMetricStats(),
                respiration=DailyMetricStats(),
                hrv=DailyHrvStats(),
                sleep=DailySleepStats(),
                skin_temp=DailySkinTempStats(),
            )
        ]
        self.checkin_rows = [DailyCheckIn(id="check-1", date="2026-07-12", energy=4)]
        self.note_rows = [
            Note(
                id="note-1",
                date="2026-07-12",
                category="training",
                title="Legs",
                content="Fresh",
            )
        ]
        self.block_status_value: object | None = None

    def recent_runs(self, *, evidence_date: str, limit: int = 20) -> list[RunListItem]:
        self.recent_runs_calls.append(limit)
        eligible = [run for run in self.runs if run.session_date <= evidence_date]
        return list(reversed(eligible))[:limit]

    def run_detail(self, run_id: str) -> RunDetailResponse:
        run = next((item for item in self.runs if item.id == run_id), None)
        if run is None:
            raise LookupError(f"Run {run_id} not found")
        return RunDetailResponse(
            session=RunningActivitySession(
                id=run.id,
                source_file=f"{run.id}.fit",
                session_date=run.session_date,
                start_time_local=run.start_time_local,
                activity_name=run.activity_name,
                timer_time_s=run.timer_time_s,
                avg_heart_rate_bpm=run.avg_heart_rate_bpm,
                hr_source=run.hr_source,
                has_heart_rate=True,
                training_load=run.training_load,
                aerobic_training_effect=run.aerobic_training_effect,
            ),
            display=RunDisplayStats(
                distance_mi=run.distance_mi,
                pace_min_per_mi=run.pace_min_per_mi,
            ),
        )

    def run_series(self, run_id: str) -> RunSeriesResponse:
        del run_id
        return RunSeriesResponse(
            series=RunningActivitySeries(
                elapsed_s=[0, 1],
                heart_rate_bpm=[138, 140],
                cadence_spm=[172, 174],
            ),
            chart=RunChartSeries(
                elapsed_s=[0, 1],
                heart_rate_bpm=[138, 140],
                cadence_spm=[172, 174],
                pace_min_per_mi=[8.1, 8.0],
            ),
            pace_min_per_mi=[8.1, 8.0],
        )

    def recovery_overview(self) -> DashboardOverviewResponse | None:
        return self.overview

    def daily_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        del last_n
        return self.metrics

    def training_today(self, target: str) -> TrainingTodayResponse:
        return TrainingTodayResponse(date=target, cards=[])

    def training_window(self, start: str, days: int) -> TrainingScheduleWindow:
        return TrainingScheduleWindow(
            start_date=start,
            end_date=(date.fromisoformat(start) + timedelta(days=days - 1)).isoformat(),
            days=[],
        )

    def block_status(self):
        return self.block_status_value

    def checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        del last_n
        return self.checkin_rows

    def notes(self, *, last_n: int | None = None) -> list[Note]:
        del last_n
        return self.note_rows


@pytest.fixture
def fake_plots(monkeypatch):
    def library(cache_dir: Path, detail, series) -> Path:
        del series
        path = cache_dir / f"{detail.session.id}-panel.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"panel")
        return path

    def current(output_dir: Path, detail, series) -> list[Path]:
        del series
        paths = [output_dir / f"{detail.session.id}-current-{index}.png" for index in (1, 2)]
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in paths:
            path.write_bytes(b"current")
        return paths

    monkeypatch.setattr("app.domains.coach.application.workspace.render_library_panel", library)
    monkeypatch.setattr("app.domains.coach.application.workspace.render_current_run_stack", current)


def _assemble(tmp_path: Path, gateway: FakeCoachGateway, repo: FakeCoachRepository, **kwargs):
    from app.domains.coach.application.workspace import assemble_workspace

    current_run_id = kwargs.pop("current_run_id", None)
    transcript = kwargs.pop("transcript", None)
    return assemble_workspace(
        gateway,  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        directory=tmp_path / "workspace",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-07-12",
        question_md="How should I interpret this?",
        current_run_id=current_run_id,
        transcript=transcript,
        **kwargs,
    )


def _journal(
    entry_id: str,
    *,
    policy_version: int,
    takeaway: str = "Maintenance purpose achieved",
) -> JournalEntry:
    summary = RunJournalSummary(
        purpose="easy aerobic maintenance",
        outcome="completed_as_intended",
        takeaway=takeaway,
        decision_relevant_uncertainties=[],
        follow_up_triggers=[],
        comparison_tags=["easy", "strides", "strap_hr"],
        refs=[ArtifactRef(kind="run", value="run-00")],
    )
    return JournalEntry(
        id=entry_id,
        ts=NOW,
        kind="review",
        content_md=render_run_journal(summary),
        refs=summary.refs,
        source_id=f"review-{entry_id}",
        policy_version=policy_version,
        run_summary=summary,
    )


def test_workspace_excludes_legacy_memory_and_exports_active_v2_memory(
    tmp_path, fake_plots
):
    repo = FakeCoachRepository()
    repo.journal = [
        _journal("legacy", policy_version=1, takeaway="Exact timing unresolved"),
        _journal("current", policy_version=2),
    ]

    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    recent = (Path(manifest.directory) / "journal/recent.md").read_text()

    assert "Maintenance purpose achieved" in recent
    assert "Exact timing unresolved" not in recent


def test_older_journal_index_exposes_purpose_outcome_tags_and_refs(
    tmp_path, fake_plots
):
    repo = FakeCoachRepository()
    repo.journal = [
        _journal(f"entry-{index}", policy_version=2) for index in range(12)
    ]

    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    index = (Path(manifest.directory) / "journal/index.md").read_text()

    assert "easy aerobic maintenance" in index
    assert "completed as intended" in index
    assert "easy,strides,strap_hr" in index
    assert "run:run-00" in index


def test_linked_review_workspace_exports_the_complete_revision_state(
    tmp_path, fake_plots
):
    repo = FakeCoachRepository()
    repo.reviews["review-linked"] = CoachReview(
        id="review-linked",
        date="2026-07-12",
        kind="run",
        run_id="run-21",
        occurrence_key="run-am",
        status="complete",
        outcome="completed_with_material_deviation",
        confidence="moderate",
        content_md="The run drifted above its intended effort.",
        refs=[
            ArtifactRef(kind="run", value="run-21"),
            ArtifactRef(kind="plot", value="run-21-current-1.png"),
        ],
        follow_up_questions=["Was the final climb intentional?"],
        plot_observations=[
            PlotObservation(
                plot="run-21-current-1.png",
                observation="Heart rate rose while pace held steady.",
            )
        ],
        history_used=[
            HistoricalEvidenceUse(
                run_id="run-20",
                role="recent_clean",
                reason="Provides a clean comparison at the same purpose.",
                refs=[
                    ArtifactRef(kind="run", value="run-20"),
                    ArtifactRef(kind="plot", value="run-20-panel.png"),
                ],
            )
        ],
        measurement_assessment=CoachMeasurementAssessment(
            run_id="run-21",
            occurrence_key="run-am",
            status="provisional",
            rationale="The climb may explain the drift.",
        ),
        job_id="job-review",
        created_at=NOW,
        updated_at=NOW,
    )

    manifest = _assemble(
        tmp_path,
        FakeCoachGateway(),
        repo,
        current_run_id="run-21",
        linked_review_id="review-linked",
    )
    current_review = (Path(manifest.directory) / "current-review.md").read_text()

    assert "Was the final climb intentional?" in current_review
    assert "Heart rate rose while pace held steady." in current_review
    assert "Provides a clean comparison at the same purpose." in current_review
    assert "The climb may explain the drift." in current_review
    assert ArtifactRef(kind="plot", value="run-20-panel.png") in manifest.resolved_refs


def test_workspace_contains_twenty_run_digest_and_all_on_demand_files(tmp_path, fake_plots):
    manifest = _assemble(tmp_path, FakeCoachGateway(), FakeCoachRepository())
    root = Path(manifest.directory)
    digest = (root / "runs/digest.md").read_text()

    assert len([line for line in digest.splitlines() if line.startswith("- ")]) == 20
    assert digest.index("run-02") < digest.index("run-21")
    for index in range(2, 22):
        run_dir = root / f"runs/run-{index:02d}"
        assert (run_dir / "summary.md").is_file()
        assert (run_dir / "laps.md").is_file()
        assert (run_dir / "plot.png").is_file()


def test_twenty_run_boundary_and_referenced_older_run(tmp_path, fake_plots):
    repo = FakeCoachRepository()
    repo.journal = [
        JournalEntry(
            id="journal-old",
            ts=NOW,
            kind="chat",
            content_md="Compare with the earliest run.",
            refs=[ArtifactRef(kind="run", value="run-00")],
            source_id="message-1",
            policy_version=2,
        )
    ]
    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    root = Path(manifest.directory)
    digest = (root / "runs/digest.md").read_text()

    assert "run-01" not in digest
    assert "run-00" not in digest
    assert (root / "refs/runs/run-00/summary.md").is_file()
    assert "run-00" in {ref.value for ref in manifest.resolved_refs}


def test_recent_journal_is_full_archive_index_is_compact_and_semantic(tmp_path, fake_plots):
    repo = FakeCoachRepository()
    repo.journal = [
        JournalEntry(
            id=f"entry-{index:02d}",
            ts=f"2026-07-{index + 1:02d}T12:00:00Z",
            kind="chat",
            content_md=f"Semantic observation {index}. A second sentence with detail.",
            source_id=f"message-{index}",
            policy_version=2,
        )
        for index in range(12)
    ]
    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    root = Path(manifest.directory)
    recent = (root / "journal/recent.md").read_text()
    index = (root / "journal/index.md").read_text()

    assert "Semantic observation 2. A second sentence" in recent
    assert "Semantic observation 11. A second sentence" in recent
    assert "Semantic observation 0." in index
    assert "A second sentence" not in index
    assert len(list((root / "journal/archive").glob("*.md"))) == 12
    assert "pace 8 min/mi" not in recent
    assert "pace 8 min/mi" in (root / "runs/digest.md").read_text()


def test_current_run_images_are_attached_only_for_review(tmp_path, fake_plots):
    from app.domains.coach.application.workspace import assemble_workspace

    gateway = FakeCoachGateway()
    repo = FakeCoachRepository()
    review = assemble_workspace(
        gateway,  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        directory=tmp_path / "review",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-06-22",
        question_md="Review run",
        current_run_id="run-21",
        transcript=None,
    )
    chat = assemble_workspace(
        gateway,  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        directory=tmp_path / "chat",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-07-12",
        question_md="Chat",
        current_run_id=None,
        transcript=None,
    )

    assert len(review.current_images) == 2
    assert all(Path(path).is_absolute() for path in review.current_images)
    assert all((tmp_path / "cache" / Path(path).name).is_file() for path in review.current_images)
    assert chat.current_images == []


def test_reassembly_refreshes_context_and_preserves_runtime_attempts(tmp_path, fake_plots):
    gateway = FakeCoachGateway()
    repo = FakeCoachRepository()
    manifest = _assemble(tmp_path, gateway, repo)
    root = Path(manifest.directory)
    runtime = root / "_runtime/attempt-1/raw.txt"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("keep me")
    gateway.overview = None
    gateway.runs.append(
        RunListItem(
            id="run-new",
            session_date="2026-07-12",
            start_time_local="2026-07-12T06:00:00",
        )
    )

    _assemble(tmp_path, gateway, repo)

    assert runtime.read_text() == "keep me"
    assert "No recovery overview available" in (root / "recovery.md").read_text()
    assert "run-new" in (root / "runs/digest.md").read_text()


def test_missing_evidence_is_explicit_and_transcript_is_written(tmp_path, fake_plots):
    gateway = FakeCoachGateway(run_count=0)
    gateway.overview = None
    gateway.metrics = []
    message = CoachMessage(
        id="message-1",
        thread_id="thread-1",
        role="user",
        content_md="What now?",
        created_at=NOW,
    )
    from app.domains.coach.application.workspace import assemble_workspace

    manifest = assemble_workspace(
        gateway,  # type: ignore[arg-type]
        FakeCoachRepository(),  # type: ignore[arg-type]
        directory=tmp_path / "workspace",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-07-12",
        question_md="Question",
        current_run_id=None,
        transcript=[message],
    )
    root = Path(manifest.directory)

    assert "No active training block" in (root / "plan.md").read_text()
    assert "No recovery overview available" in (root / "recovery.md").read_text()
    assert "No runs available" in (root / "runs/digest.md").read_text()
    assert "What now?" in (root / "transcript.md").read_text()


def test_training_plan_uses_runtime_start_instead_of_authored_window_start(
    tmp_path,
    fake_plots,
):
    gateway = FakeCoachGateway(run_count=0)
    gateway.block_status_value = SimpleNamespace(
        block=V3Block(
            id="block1.internal_id",
            name="Threshold Development",
            identity="development",
            window=BlockWindow(start="2026-07-13", days=28),
            bundle_ids=[],
        ),
        schedule_start="2026-08-03",
    )
    from app.domains.coach.application.workspace import assemble_workspace

    manifest = assemble_workspace(
        gateway,  # type: ignore[arg-type]
        FakeCoachRepository(),  # type: ignore[arg-type]
        directory=tmp_path / "workspace",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-08-03",
        target_date="2026-08-03",
        question_md="Review Day 1",
        current_run_id=None,
        transcript=None,
    )

    plan = (Path(manifest.directory) / "plan.md").read_text()
    assert "Target block day: 1" in plan
    assert "Block window: 2026-08-03 for 28 days" in plan


def test_date_review_and_plot_refs_resolve_and_traversal_is_skipped_and_reported(
    tmp_path, fake_plots
):
    repo = FakeCoachRepository()
    repo.reviews["review-1"] = CoachReview(
        id="review-1",
        date="2026-07-11",
        kind="run",
        run_id="run-21",
        status="complete",
        verdict="compliant",
        content_md="A sound easy run.",
        job_id="job-1",
        created_at=NOW,
        updated_at=NOW,
    )
    repo.journal = [
        JournalEntry(
            id="refs",
            ts=NOW,
            kind="chat",
            content_md="Useful references.",
            refs=[
                ArtifactRef(kind="date", value="2026-07-12"),
                ArtifactRef(kind="review", value="review-1"),
                ArtifactRef(kind="plot", value="run-21-panel.png"),
            ],
            source_id="message-1",
            policy_version=2,
        )
    ]
    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    root = Path(manifest.directory)

    assert "Fresh" in (root / "refs/dates/2026-07-12.md").read_text()
    assert "A sound easy run" in (root / "refs/reviews/review-1.md").read_text()
    assert (root / "refs/plots/run-21-panel.png").is_file()

    repo.journal[0] = repo.journal[0].model_copy(
        update={"refs": [ArtifactRef(kind="review", value="../escape")]}
    )
    unsafe_manifest = _assemble(tmp_path / "unsafe", FakeCoachGateway(), repo)
    unsafe_root = Path(unsafe_manifest.directory)

    assert unsafe_manifest.resolved_refs == []
    assert "Unsafe artifact reference" in (unsafe_root / "refs/unavailable.md").read_text()


def test_historical_workspace_plot_ref_backfills_missing_shared_cache(tmp_path, fake_plots):
    repo = FakeCoachRepository()
    repo.journal = [
        JournalEntry(
            id="legacy-plot-ref",
            ts=NOW,
            kind="review",
            content_md="Retain the plot used by the prior review.",
            refs=[ArtifactRef(kind="plot", value="legacy-current-p01.png")],
            source_id="review-old",
            policy_version=2,
        )
    ]
    workspaces = tmp_path / "workspaces"
    legacy_plot = (
        workspaces
        / "reviews/review-old/current/run-21/images/legacy-current-p01.png"
    )
    legacy_plot.parent.mkdir(parents=True)
    legacy_plot.write_bytes(b"legacy plot")

    from app.domains.coach.application.workspace import assemble_workspace

    manifest = assemble_workspace(
        FakeCoachGateway(),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        directory=workspaces / "reviews/review-new",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-07-12",
        question_md="Review run",
        current_run_id=None,
        transcript=None,
    )

    root = Path(manifest.directory)
    assert (tmp_path / "cache/legacy-current-p01.png").read_bytes() == b"legacy plot"
    assert (root / "refs/plots/legacy-current-p01.png").read_bytes() == b"legacy plot"


def test_stale_plot_ref_is_skipped_and_reported(tmp_path, fake_plots):
    repo = FakeCoachRepository()
    repo.reviews["review-1"] = CoachReview(
        id="review-1",
        date="2026-07-11",
        kind="run",
        run_id="run-21",
        status="complete",
        verdict="compliant",
        content_md="A sound easy run.",
        job_id="job-1",
        created_at=NOW,
        updated_at=NOW,
    )
    repo.journal = [
        JournalEntry(
            id="refs",
            ts=NOW,
            kind="chat",
            content_md="One valid ref and one plot that no longer exists.",
            refs=[
                ArtifactRef(kind="review", value="review-1"),
                ArtifactRef(kind="plot", value="missing-panel.png"),
            ],
            source_id="message-1",
            policy_version=2,
        )
    ]

    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    root = Path(manifest.directory)
    unavailable = (root / "refs/unavailable.md").read_text()

    assert "plot:missing-panel.png" in unavailable
    assert "A sound easy run" in (root / "refs/reviews/review-1.md").read_text()
    assert {ref.value for ref in manifest.resolved_refs} == {"review-1"}


def test_stale_run_ref_is_skipped_and_reported(tmp_path, fake_plots):
    repo = FakeCoachRepository()
    repo.journal = [
        JournalEntry(
            id="refs",
            ts=NOW,
            kind="chat",
            content_md="One valid run ref and one run that no longer exists.",
            refs=[
                ArtifactRef(kind="run", value="run-00"),
                ArtifactRef(kind="run", value="run-missing"),
            ],
            source_id="message-1",
            policy_version=2,
        )
    ]

    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    root = Path(manifest.directory)
    unavailable = (root / "refs/unavailable.md").read_text()

    assert "run:run-missing" in unavailable
    assert (root / "refs/runs/run-00/summary.md").is_file()
    assert not (root / "refs/runs/run-missing").exists()
    assert {ref.value for ref in manifest.resolved_refs} == {"run-00"}


def test_run_ref_failing_after_partial_writes_leaves_no_destination_dir(
    tmp_path, monkeypatch
):
    """A run ref that fails late (after summary.md/laps.md are written) must not
    leave `refs/runs/<id>` behind — a model must never see a half-written ref dir
    as if it were complete."""

    def library(cache_dir: Path, detail, series) -> Path:
        del series
        if detail.session.id == "run-00":
            # Simulate a source panel that never materializes: summary.md and
            # laps.md for this ref are already written by the time the final
            # `shutil.copy2` in `_export_run` is attempted, and that copy raises.
            return cache_dir / "run-00-missing-panel.png"
        path = cache_dir / f"{detail.session.id}-panel.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"panel")
        return path

    def current(output_dir: Path, detail, series) -> list[Path]:
        del series
        paths = [output_dir / f"{detail.session.id}-current-{index}.png" for index in (1, 2)]
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in paths:
            path.write_bytes(b"current")
        return paths

    monkeypatch.setattr("app.domains.coach.application.workspace.render_library_panel", library)
    monkeypatch.setattr("app.domains.coach.application.workspace.render_current_run_stack", current)

    repo = FakeCoachRepository()
    repo.journal = [
        JournalEntry(
            id="refs",
            ts=NOW,
            kind="chat",
            content_md="Reference an older run whose plot copy fails.",
            refs=[ArtifactRef(kind="run", value="run-00")],
            source_id="message-1",
            policy_version=2,
        )
    ]

    manifest = _assemble(tmp_path, FakeCoachGateway(), repo)
    root = Path(manifest.directory)
    unavailable = (root / "refs/unavailable.md").read_text()

    assert "run:run-00" in unavailable
    assert not (root / "refs/runs/run-00").exists()
    assert "run-00" not in {ref.value for ref in manifest.resolved_refs}


def test_current_run_context_does_not_scan_recent_runs(tmp_path, fake_plots):
    """Reviewing a current run must call `recent_runs` exactly once, bounded by
    `historical_run_limit` — not scan the full run history — while still
    producing the current-run evidence files."""
    from app.domains.coach.application.workspace import assemble_workspace

    gateway = FakeCoachGateway()
    repo = FakeCoachRepository()

    manifest = assemble_workspace(
        gateway,  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        directory=tmp_path / "workspace",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-07-12",
        question_md="Review this run",
        current_run_id="run-21",
        transcript=None,
        historical_run_limit=20,
    )
    root = Path(manifest.directory)

    assert gateway.recent_runs_calls == [20]
    assert (root / "current/run-21/summary.md").is_file()
    assert (root / "current/run-21/laps.md").is_file()
