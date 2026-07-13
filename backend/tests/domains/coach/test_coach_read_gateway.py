"""Tests for the coach's single cross-domain evidence seam."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

import pytest

import app.domains.coach.read_gateway as gateway_module
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.garmin_analytics.application.dependencies import (
    BiometricReadRepository,
)
from app.domains.garmin_analytics.contracts import (
    DashboardOverviewResponse,
    RunDetailResponse,
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
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
)
from app.domains.journal.contracts import DailyCheckIn, Note
from app.domains.training.contracts import (
    TrainingMeasurementAssessment,
    TrainingRunActivitySummary,
    TrainingRunEvidence,
    TrainingScheduleWindow,
    TrainingTodayResponse,
)
from app.domains.training.dependencies import (
    MeasurementAssessmentReadPort,
    RunActivityReadPort,
    TrainingRepository,
)


class FakeRunsRepository:
    def __init__(self, sessions: list[RunningActivitySession]) -> None:
        self.sessions = sessions
        self.laps: dict[str, list[RunningActivityLap]] = {}
        self.series: dict[str, RunningActivitySeries] = {}

    def load_sessions(self) -> list[RunningActivitySession]:
        return list(self.sessions)

    def load_session(self, run_id: str) -> RunningActivitySession | None:
        return next((session for session in self.sessions if session.id == run_id), None)

    def load_laps(self, run_id: str) -> list[RunningActivityLap]:
        return list(self.laps.get(run_id, []))

    def load_series(self, run_id: str) -> RunningActivitySeries | None:
        return self.series.get(run_id)


class FakeBiometricsRepository:
    def __init__(self, metrics: list[DailyMetric]) -> None:
        self.metrics = metrics

    def load_daily_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        if last_n is None:
            return list(self.metrics)
        return list(self.metrics[-last_n:])


class FailingBiometricsRepository(FakeBiometricsRepository):
    def load_daily_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        del last_n
        raise RuntimeError("database unavailable")


class FakeJournalRepository:
    def __init__(self) -> None:
        self.checkin_limits: list[int | None] = []
        self.note_limits: list[int | None] = []

    def list_checkins(
        self, *, date: str | None = None, last_n: int | None = None
    ) -> list[DailyCheckIn]:
        assert date is None
        self.checkin_limits.append(last_n)
        return [DailyCheckIn(id="checkin-1", date="2026-07-11", energy=4)]

    def list_notes(self, *, date: str | None = None, last_n: int | None = None) -> list[Note]:
        assert date is None
        self.note_limits.append(last_n)
        return [
            Note(
                id="note-1",
                date="2026-07-11",
                category="training",
                title="Easy effort",
                content="Felt controlled",
            )
        ]


class FakeRunActivityPort:
    def runs_between(self, start_date: str, end_date: str) -> list[TrainingRunActivitySummary]:
        del start_date, end_date
        return []

    def evidence_for_run(self, run_id: str) -> TrainingRunEvidence:
        raise LookupError(f"run evidence not configured for {run_id}")


class FakeMeasurementAssessmentPort:
    def latest_for(
        self,
        *,
        run_id: str,
        occurrence_key: str,
        before: str | None = None,
    ) -> TrainingMeasurementAssessment | None:
        del run_id, occurrence_key, before
        return None


def _session(index: int, session_date: str) -> RunningActivitySession:
    return RunningActivitySession(
        id=f"run-{index:02d}",
        source_file=f"run-{index:02d}.fit",
        session_date=session_date,
        start_time_local=f"{session_date}T06:00:00",
        activity_name=f"Run {index}",
        distance_m=1609.344,
        pace_min_per_km=5.0,
        timer_time_s=1500,
        avg_heart_rate_bpm=140,
        has_heart_rate=True,
    )


def _metric(metric_date: str) -> DailyMetric:
    return DailyMetric(
        date=metric_date,
        heart_rate=DailyHeartRateStats(avg=60, min=45, max=120, resting=48),
        stress=DailyMetricStats(avg=20),
        body_battery=DailyBodyBatteryStats(avg=65),
        spo2=DailyMetricStats(avg=97),
        respiration=DailyMetricStats(avg=14),
        hrv=DailyHrvStats(nightly_avg=55),
        sleep=DailySleepStats(score=85),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


def _gateway(
    *,
    runs: FakeRunsRepository,
    biometrics: FakeBiometricsRepository | None = None,
    journal: FakeJournalRepository | None = None,
    training_repo: object | None = None,
    run_activity_port: RunActivityReadPort | None = None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None = None,
) -> CoachReadGateway:
    return CoachReadGateway(
        runs_repo=runs,
        biometrics_repo=cast(BiometricReadRepository, biometrics or FakeBiometricsRepository([])),
        training_repo=cast(TrainingRepository, training_repo or object()),
        run_activity_port=run_activity_port or FakeRunActivityPort(),
        measurement_assessment_port=(
            measurement_assessment_port or FakeMeasurementAssessmentPort()
        ),
        journal_repo=cast(Any, journal or FakeJournalRepository()),
    )


def test_recent_runs_respects_evidence_date_and_twenty_run_limit():
    start = date(2026, 6, 1)
    sessions = [_session(index, (start + timedelta(days=index)).isoformat()) for index in range(25)]
    gateway = _gateway(runs=FakeRunsRepository(sessions))

    runs = gateway.recent_runs(evidence_date="2026-06-24")

    assert len(runs) == 20
    assert [run.session_date for run in runs] == sorted(
        [run.session_date for run in runs], reverse=True
    )
    assert runs[0].session_date == "2026-06-24"
    assert runs[-1].session_date == "2026-06-05"


def test_run_detail_and_series_use_existing_imperial_projections():
    repository = FakeRunsRepository([_session(1, "2026-07-11")])
    repository.laps["run-01"] = [
        RunningActivityLap(lap_index=1, distance_m=1609.344, pace_min_per_km=5.0)
    ]
    repository.series["run-01"] = RunningActivitySeries(
        elapsed_s=list(range(11)),
        distance_m=cast(list[float | None], [1609.344] * 11),
        speed_mps=cast(list[float | None], [3.0] * 11),
        altitude_m=cast(list[float | None], [100.0] * 11),
    )
    gateway = _gateway(runs=repository)

    detail = gateway.run_detail("run-01")
    series = gateway.run_series("run-01")

    assert isinstance(detail, RunDetailResponse)
    assert detail.display.distance_mi == 1.0
    assert detail.display.pace_min_per_mi == 8.05
    assert detail.display.lap_display[0].distance_mi == 1.0
    assert isinstance(series, RunSeriesResponse)
    assert series.distance_mi == [1.0] * 11
    assert series.altitude_ft == [328.0] * 11
    assert series.pace_min_per_mi == [None] * 10 + [8.941]


def test_recovery_overview_returns_none_only_for_no_metrics():
    gateway = _gateway(runs=FakeRunsRepository([]))

    assert gateway.recovery_overview() is None

    failing = _gateway(runs=FakeRunsRepository([]), biometrics=FailingBiometricsRepository([]))
    with pytest.raises(RuntimeError, match="database unavailable"):
        failing.recovery_overview()


def test_recovery_and_daily_metrics_return_existing_contracts():
    biometrics = FakeBiometricsRepository([_metric("2026-07-11")])
    gateway = _gateway(runs=FakeRunsRepository([]), biometrics=biometrics)

    overview = gateway.recovery_overview()
    metrics = gateway.daily_metrics(last_n=1)

    assert isinstance(overview, DashboardOverviewResponse)
    assert metrics == biometrics.metrics


def test_training_today_receives_run_activity_port_for_association(monkeypatch):
    training_repo = object()
    run_activity_port = FakeRunActivityPort()
    assessment_port = FakeMeasurementAssessmentPort()
    captured: dict[str, object] = {}

    def fake_today(
        repo,
        *,
        date: str,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        captured.update(
            repo=repo,
            date=date,
            run_activity_port=run_activity_port,
            measurement_assessment_port=measurement_assessment_port,
        )
        return TrainingTodayResponse(date=date, cards=[])

    monkeypatch.setattr(gateway_module.training_uc, "get_training_today", fake_today)
    gateway = _gateway(
        runs=FakeRunsRepository([]),
        training_repo=training_repo,
        run_activity_port=run_activity_port,
        measurement_assessment_port=assessment_port,
    )

    result = gateway.training_today("2026-07-11")

    assert result == TrainingTodayResponse(date="2026-07-11", cards=[])
    assert captured == {
        "repo": training_repo,
        "date": "2026-07-11",
        "run_activity_port": run_activity_port,
        "measurement_assessment_port": assessment_port,
    }


def test_training_window_and_block_status_delegate(monkeypatch):
    training_repo = object()
    run_activity_port = FakeRunActivityPort()
    assessment_port = FakeMeasurementAssessmentPort()
    calls: list[tuple[object, str, int, object, object]] = []

    def fake_window(
        repo,
        *,
        start_date: str,
        duration_days: int = 14,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        calls.append(
            (
                repo,
                start_date,
                duration_days,
                run_activity_port,
                measurement_assessment_port,
            )
        )
        return TrainingScheduleWindow(start_date=start_date, end_date="2026-07-17", days=[])

    monkeypatch.setattr(gateway_module.training_uc, "get_training_schedule_window", fake_window)
    monkeypatch.setattr(gateway_module.training_uc, "get_block_status", lambda repo: None)
    gateway = _gateway(
        runs=FakeRunsRepository([]),
        training_repo=training_repo,
        run_activity_port=run_activity_port,
        measurement_assessment_port=assessment_port,
    )

    window = gateway.training_window("2026-07-11", days=7)

    assert window.end_date == "2026-07-17"
    assert calls == [(training_repo, "2026-07-11", 7, run_activity_port, assessment_port)]
    assert gateway.block_status() is None


def test_checkins_and_notes_delegate_without_copying_journal_policy():
    journal = FakeJournalRepository()
    gateway = _gateway(runs=FakeRunsRepository([]), journal=journal)

    checkins = gateway.checkins(last_n=5)
    notes = gateway.notes(last_n=8)

    assert checkins[0].id == "checkin-1"
    assert notes[0].id == "note-1"
    assert journal.checkin_limits == [5]
    assert journal.note_limits == [8]
