"""HRV raw-period aggregate calculations."""

from app.domains.garmin_analytics.contracts import PeriodHrvStats
from app.domains.garmin_health.contracts import DayData
from app.domains.garmin_health.domain.daily_metrics.hrv import (
    is_balanced_hrv_status,
)
from app.utils.numeric import safe_avg


def compute_period_hrv(days: list[DayData]) -> PeriodHrvStats:
    nightly_values: list[float] = []
    weekly_values: list[float] = []
    statuses: list[str] = []
    for day in days:
        if day.hrv.hrv_summaries:
            summary = day.hrv.hrv_summaries[0]
            if summary.last_night_average is not None:
                nightly_values.append(summary.last_night_average)
            if summary.weekly_average is not None:
                weekly_values.append(summary.weekly_average)
            if summary.status:
                statuses.append(summary.status)

    balanced = sum(1 for status in statuses if is_balanced_hrv_status(status))
    return PeriodHrvStats(
        avg_nightly=safe_avg(nightly_values),
        avg_weekly=safe_avg(weekly_values),
        balanced_pct=round(balanced / len(statuses) * 100) if statuses else None,
        total_days=len(statuses),
    )
