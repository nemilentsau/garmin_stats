"""Preview use-case tests for experiment design validation boundaries."""

from __future__ import annotations

from typing import Any, cast

from app.domains.experiments.application.preview import preview_experiment
from app.domains.experiments.contracts import Experiment, ExperimentDesign, OutcomeMetric
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
)
from app.domains.routines.contracts import RoutineSchedule


def _make_metric(date: str, *, hrv_nightly: float = 45.0) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(),
        stress=DailyMetricStats(),
        body_battery=DailyBodyBatteryStats(),
        spo2=DailyMetricStats(),
        respiration=DailyMetricStats(),
        hrv=DailyHrvStats(nightly_avg=hrv_nightly),
        sleep=DailySleepStats(),
        skin_temp=DailySkinTempStats(),
    )


class _PreviewRepo:
    def experiment_exists(self, experiment_id: str) -> bool:
        return False


class _ReadSource:
    def __init__(self, metrics: list[DailyMetric]):
        self._metrics = metrics

    def list_daily_metrics(self) -> list[DailyMetric]:
        return self._metrics


class _RoutineRepo:
    def __init__(self, routine: RoutineSchedule | None):
        self._routine = routine

    def get_routine(self, routine_id: str) -> RoutineSchedule | None:
        return self._routine if self._routine and self._routine.id == routine_id else None


def test_preview_resolves_routine_dates_without_mutating_input_experiment():
    """Routine-derived dates should be returned on a copied preview experiment."""
    routine = RoutineSchedule(
        id="routine-1",
        name="Routine One",
        start_date="2026-01-10",
        end_date="2026-01-20",
    )
    experiment = Experiment(
        id="date-preview",
        name="Date Preview",
        status="draft",
        design=ExperimentDesign(baseline_duration_days=3),
        linked_routine_ids=[routine.id],
        outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
    )
    original_payload = experiment.model_dump()

    result = preview_experiment(
        cast(Any, _PreviewRepo()),
        _ReadSource([
            _make_metric("2026-01-07"),
            _make_metric("2026-01-08"),
            _make_metric("2026-01-09"),
        ]),
        experiment,
        routine_repo=cast(Any, _RoutineRepo(routine)),
    )

    assert experiment.model_dump() == original_payload
    assert result.experiment is not None
    assert result.experiment.design is not None
    assert result.experiment.design.baseline_start_date == "2026-01-07"
    assert result.experiment.design.baseline_end_date == "2026-01-09"
    assert result.experiment.design.treatment_start_date == "2026-01-10"
    assert result.experiment.design.treatment_end_date == "2026-01-20"
