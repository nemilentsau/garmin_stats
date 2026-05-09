"""Stress daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailyMetricStats, DayWellness

from .common import compute_daily_metric_stats


def compute_daily_stress(wellness: DayWellness) -> DailyMetricStats:
    values = [r.value for r in wellness.stress]
    return compute_daily_metric_stats(values)
