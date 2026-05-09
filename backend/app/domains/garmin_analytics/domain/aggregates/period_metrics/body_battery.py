"""Body battery raw-period aggregate calculations."""

from app.domains.garmin_analytics.contracts import PeriodBodyBatteryStats
from app.domains.garmin_health.contracts import DayData
from app.utils.numeric import safe_avg


def compute_period_body_battery(days: list[DayData]) -> PeriodBodyBatteryStats:
    mins: list[float] = []
    maxes: list[float] = []
    for day in days:
        values = [r.value for r in day.wellness.body_battery]
        if values:
            mins.append(min(values))
            maxes.append(max(values))

    return PeriodBodyBatteryStats(
        avg_min=safe_avg(mins),
        avg_max=safe_avg(maxes),
        days_tracked=len(mins),
    )
