"""Integration tests for bounded, refreshable coach evidence workspaces."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.domains.coach.contracts import (
    ArtifactRef,
    BriefVersion,
    CoachMessage,
    CoachReview,
    JournalEntry,
)
from app.domains.garmin_analytics.contracts import (
    DashboardOverviewResponse,
    EvidenceRow,
    MeaningfulChange,
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
    TrainingScheduleWindow,
    TrainingTodayResponse,
)

NOW = "2026-07-12T12:00:00Z"


class FakeCoachRepository:
    def __init__(self) -> None:
        self.journal: list[JournalEntry] = []
        self.brief: BriefVersion | None = None
        self.reviews: dict[str, CoachReview] = {}

    def list_journal(self, *, limit: int | None = None) -> list[JournalEntry]:
        return self.journal if limit is None else self.journal[-limit:]

    def current_brief(self) -> BriefVersion | None:
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
            )
            for index in range(run_count)
        ]
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

    def recent_runs(self, *, evidence_date: str, limit: int = 20) -> list[RunListItem]:
        eligible = [run for run in self.runs if run.session_date <= evidence_date]
        return list(reversed(eligible))[:limit]

    def run_detail(self, run_id: str) -> RunDetailResponse:
        run = next(run for run in self.runs if run.id == run_id)
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
        return None

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

    return assemble_workspace(
        gateway,  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        directory=tmp_path / "workspace",
        plot_cache_dir=tmp_path / "cache",
        evidence_date="2026-07-12",
        target_date="2026-07-12",
        question_md="How should I interpret this?",
        current_run_id=None,
        transcript=None,
        **kwargs,
    )


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


def test_date_review_and_plot_refs_resolve_and_traversal_is_rejected(tmp_path, fake_plots):
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
    with pytest.raises(ValueError, match="Unsafe artifact reference"):
        _assemble(tmp_path / "unsafe", FakeCoachGateway(), repo)
