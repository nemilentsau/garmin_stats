"""Body battery daily aggregate calculations."""

from typing import cast

from app.domains.garmin_analytics.contracts import (
    DailyBodyBatteryStats,
    DayWellness,
)
from app.domains.garmin_analytics.domain.primitives.numeric import (
    summarize_scalar_values,
)


def compute_daily_body_battery(wellness: DayWellness) -> DailyBodyBatteryStats:
    values = [r.value for r in wellness.body_battery]
    summary = summarize_scalar_values(values)
    return DailyBodyBatteryStats(
        avg=summary.avg,
        min=cast("int | None", summary.min),
        max=cast("int | None", summary.max),
        median=summary.median,
        q1=summary.q1,
        q3=summary.q3,
    )
