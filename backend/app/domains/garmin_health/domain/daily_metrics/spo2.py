"""SpO2 daily metric calculations."""

from app.domains.garmin_health.contracts import DailyMetricStats, DayWellness

from .common import compute_daily_metric_stats


def compute_daily_spo2(wellness: DayWellness) -> DailyMetricStats:
    """Compute persisted daily SpO2 stats from wellness readings."""
    values = [r.value for r in wellness.spo2]
    return compute_daily_metric_stats(values)
