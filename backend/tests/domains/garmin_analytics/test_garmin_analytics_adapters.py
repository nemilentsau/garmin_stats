"""Tests for Garmin analytics persistence adapters."""

from app.domains.garmin_analytics import adapters
from app.domains.garmin_analytics.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayWellness,
)
from app.infra.sqlite import connect


def _make_daily_metric(date: str) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, resting=48),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(min=40, max=90),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(weekly_avg=52.0, nightly_avg=50.0),
        sleep=DailySleepStats(score=82),
        skin_temp=DailySkinTempStats(deviation=0.2),
    )


def test_adapter_loads_wellness_for_requested_date():
    for date in ["2026-01-15", "2026-01-16"]:
        wellness = DayWellness(date=date)
        with connect() as con:
            con.execute(
                "INSERT INTO wellness_data (date, data, updated_at) VALUES (?, ?, ?)",
                (date, wellness.model_dump_json(), "2026-01-15T00:00:00Z"),
            )
            con.commit()

    loaded = adapters.load_wellness("2026-01-15")

    assert [day.date for day in loaded] == ["2026-01-15"]


def test_adapter_loads_daily_metrics_ordered_by_date():
    for date in ["2026-01-16", "2026-01-15"]:
        metric = _make_daily_metric(date)
        with connect() as con:
            con.execute(
                "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                (date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
            )
            con.commit()

    loaded = adapters.load_daily_metrics()

    assert [metric.date for metric in loaded] == ["2026-01-15", "2026-01-16"]
    assert loaded[0].heart_rate.avg == 70.0
    assert loaded[0].heart_rate.resting == 48
