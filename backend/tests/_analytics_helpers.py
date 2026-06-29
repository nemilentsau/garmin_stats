"""Shared builders for Garmin-analytics tests.

One construction site for the ~12-field ``DailyMetric`` and the ``daily_metrics`` insert,
so a contract change (a new or renamed field) touches this file instead of every analytics
test module. The builder's defaults match the historical per-file builders; pass overrides
for the fields a given test actually exercises.
"""

import app.infra.sqlite as sqlite
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
)


def make_daily_metric(
    date: str,
    nightly_avg: float | None = None,
    weekly_avg: float | None = 50.0,
    hrv_status: str | None = "balanced",
    sleep_score: int | None = 80,
    resting_hr: int | None = 46,
) -> DailyMetric:
    """Build a ``DailyMetric`` with only HRV-relevant fields parameterized.

    Positional-or-keyword so both call styles in the analytics suite work: the trend tests
    pass ``date``/``nightly_avg`` only, while the insight tests pass the full HRV/sleep/HR set.
    """
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, median=72.0, resting=resting_hr),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(nightly_avg=nightly_avg, weekly_avg=weekly_avg, status=hrv_status),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


def insert_metric(metric: DailyMetric) -> None:
    """Persist one ``DailyMetric`` into the ``daily_metrics`` table of the active test DB."""
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
            (metric.date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()
