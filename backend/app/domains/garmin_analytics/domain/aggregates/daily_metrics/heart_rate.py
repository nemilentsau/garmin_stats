"""Heart-rate daily aggregate calculations."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import (
    DailyHeartRateStats,
    DayWellness,
    HRZoneBucket,
)

from .common import compute_daily_int_extrema_stats

# HR zone definitions: (label, lower_bound_inclusive, upper_bound_exclusive_or_None)
HR_ZONE_THRESHOLDS: list[tuple[str, int, int | None]] = [
    ("Rest", 0, 60),
    ("Light", 60, 100),
    ("Moderate", 100, 130),
    ("Vigorous", 130, None),
]


def compute_hr_zones(hr_values: Sequence[int]) -> list[HRZoneBucket]:
    """Bucket HR readings into zones and return counts + percentages."""
    if not hr_values:
        return []
    counts = [0] * len(HR_ZONE_THRESHOLDS)
    for v in hr_values:
        for i, (_, low, high) in enumerate(HR_ZONE_THRESHOLDS):
            if v >= low and (high is None or v < high):
                counts[i] += 1
                break
    total = sum(counts)
    if total == 0:
        return []
    return [
        HRZoneBucket(
            label=label,
            min_bpm=low,
            max_bpm=high,
            count=counts[i],
            pct=round(counts[i] / total * 100),
        )
        for i, (label, low, high) in enumerate(HR_ZONE_THRESHOLDS)
        if counts[i] > 0
    ]


def compute_daily_heart_rate(wellness: DayWellness) -> DailyHeartRateStats:
    values = [r.value for r in wellness.heart_rate if r.value > 0]
    stats = compute_daily_int_extrema_stats(values)
    return DailyHeartRateStats(
        avg=stats.avg,
        min=stats.min,
        max=stats.max,
        median=stats.median,
        q1=stats.q1,
        q3=stats.q3,
        resting=latest_resting_hr(wellness),
        zones=compute_hr_zones(values),
    )


def latest_resting_hr(wellness: DayWellness) -> int | None:
    """Return Garmin's latest resting HR, preferring current-day values."""
    value: int | None = None
    for reading in wellness.resting_hr:
        current = reading.current_day_resting_hr or reading.resting_hr
        if current:
            value = current
    return value
