"""SpO2 daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailyMetricStats, DayWellness

from .common import compute_daily_metric_stats


def compute_daily_spo2(wellness: DayWellness) -> DailyMetricStats:
    values = [r.value for r in wellness.spo2]
    return compute_daily_metric_stats(values)
