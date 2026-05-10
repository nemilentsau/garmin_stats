"""Respiration daily metric calculations."""

from app.domains.garmin_health.contracts import DailyMetricStats, DayWellness

from .common import compute_daily_metric_stats


def compute_daily_respiration(wellness: DayWellness) -> DailyMetricStats:
    """Compute persisted daily respiration stats from wellness readings."""
    values = [r.value for r in wellness.respiration]
    return compute_daily_metric_stats(values, rounded_extrema=True)
