"""Body Battery daily metric calculations."""

from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DayWellness,
)

from .common import compute_daily_int_extrema_stats


def compute_daily_body_battery(wellness: DayWellness) -> DailyBodyBatteryStats:
    """Compute persisted daily Body Battery stats from wellness readings."""
    values = [r.value for r in wellness.body_battery]
    stats = compute_daily_int_extrema_stats(values)
    return DailyBodyBatteryStats(
        avg=stats.avg,
        min=stats.min,
        max=stats.max,
        median=stats.median,
        q1=stats.q1,
        q3=stats.q3,
    )
