"""Preview use-case tests for experiment design validation boundaries."""

from __future__ import annotations

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


def test_preview_requires_explicit_design_dates_without_mutating_input_experiment():
    experiment = Experiment(
        id="date-preview",
        name="Date Preview",
        status="draft",
        design=ExperimentDesign(),
        outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
    )
    original_payload = experiment.model_dump()

    result = preview_experiment(
        _PreviewRepo(),
        _ReadSource([
            _make_metric("2026-01-07"),
            _make_metric("2026-01-08"),
            _make_metric("2026-01-09"),
        ]),
        experiment,
    )

    assert experiment.model_dump() == original_payload
    assert result.valid is False
    assert result.experiment == experiment
    assert [issue.message for issue in result.issues] == [
        "Baseline start, baseline end, and treatment start dates are required."
    ]
