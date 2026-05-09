"""Heart-rate period summary calculations from raw readings."""

from app.domains.garmin_analytics.contracts import PeriodHeartRateStats
from app.domains.garmin_health.contracts import DayData
from app.domains.garmin_health.domain.daily_metrics.heart_rate import (
    compute_hr_zones,
    latest_resting_hr,
)
from app.utils.numeric import (
    safe_avg,
    safe_percentile,
)


def compute_period_heart_rate(days: list[DayData]) -> PeriodHeartRateStats:
    """Compute period heart-rate stats from raw readings and resting HR rows."""
    values = [r.value for day in days for r in day.wellness.heart_rate if r.value > 0]
    resting_values: list[int] = []
    for day in days:
        resting = latest_resting_hr(day.wellness)
        if resting is not None:
            resting_values.append(resting)

    return PeriodHeartRateStats(
        avg=safe_avg(values),
        avg_resting=safe_avg(resting_values),
        typical_low=safe_percentile(values, 25),
        typical_high=safe_percentile(values, 75),
        zones=compute_hr_zones(values),
    )
