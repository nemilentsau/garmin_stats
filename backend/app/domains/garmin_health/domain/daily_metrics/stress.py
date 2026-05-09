"""Stress daily metric calculations."""

from app.domains.garmin_health.contracts import DailyMetricStats, DayWellness

from .common import compute_daily_metric_stats


def compute_daily_stress(wellness: DayWellness) -> DailyMetricStats:
    """Compute persisted daily stress stats from wellness readings."""
    values = [r.value for r in wellness.stress]
    return compute_daily_metric_stats(values)
