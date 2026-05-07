"""Respiration daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailyMetricStats, DayWellness

from .common import compute_daily_metric_stats


def compute_daily_respiration(wellness: DayWellness) -> DailyMetricStats:
    values = [r.value for r in wellness.respiration]
    return compute_daily_metric_stats(values, rounded_extrema=True)
