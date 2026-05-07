"""Heart-rate raw-period aggregate calculations."""

from app.domains.garmin_analytics.contracts import DayData, PeriodHeartRateStats
from app.domains.garmin_analytics.domain.aggregates.daily_metrics.heart_rate import (
    compute_hr_zones,
)
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_percentile,
)


def compute_period_heart_rate(days: list[DayData]) -> PeriodHeartRateStats:
    values = [r.value for day in days for r in day.wellness.heart_rate if r.value > 0]
    resting_values: list[int] = []
    for day in days:
        resting = _latest_resting_hr(day)
        if resting is not None:
            resting_values.append(resting)

    return PeriodHeartRateStats(
        avg=safe_avg(values),
        avg_resting=safe_avg(resting_values),
        typical_low=safe_percentile(values, 25),
        typical_high=safe_percentile(values, 75),
        zones=compute_hr_zones(values),
    )


def _latest_resting_hr(day: DayData) -> int | None:
    value: int | None = None
    for reading in day.wellness.resting_hr:
        current = reading.current_day_resting_hr or reading.resting_hr
        if current:
            value = current
    return value
