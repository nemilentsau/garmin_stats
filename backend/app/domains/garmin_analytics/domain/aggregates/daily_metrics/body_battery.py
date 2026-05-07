"""Body battery daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import (
    DailyBodyBatteryStats,
    DayWellness,
)
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_median,
    safe_percentile,
)


def compute_daily_body_battery(wellness: DayWellness) -> DailyBodyBatteryStats:
    values = [r.value for r in wellness.body_battery]
    return DailyBodyBatteryStats(
        avg=safe_avg(values),
        min=min(values) if values else None,
        max=max(values) if values else None,
        median=safe_median(values),
        q1=safe_percentile(values, 25),
        q3=safe_percentile(values, 75),
    )
