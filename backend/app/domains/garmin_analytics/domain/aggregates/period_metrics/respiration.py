"""Respiration period summary calculations from raw readings."""

from app.domains.garmin_analytics.contracts import PeriodMetricStats
from app.domains.garmin_health.contracts import DayData

from .common import compute_period_metric_stats


def compute_period_respiration(days: list[DayData]) -> PeriodMetricStats:
    """Compute period respiration stats from raw wellness readings."""
    values = [r.value for day in days for r in day.wellness.respiration]
    return compute_period_metric_stats(values)
