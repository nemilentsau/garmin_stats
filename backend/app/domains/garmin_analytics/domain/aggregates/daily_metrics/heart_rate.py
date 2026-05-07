"""Heart-rate daily aggregate calculations."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import (
    DailyHeartRateStats,
    DayWellness,
    HRZoneBucket,
)
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_median,
    safe_percentile,
)

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
    return DailyHeartRateStats(
        avg=safe_avg(values),
        min=min(values) if values else None,
        max=max(values) if values else None,
        median=safe_median(values),
        q1=safe_percentile(values, 25),
        q3=safe_percentile(values, 75),
        resting=_latest_resting_hr(wellness),
        zones=compute_hr_zones(values),
    )


def _latest_resting_hr(wellness: DayWellness) -> int | None:
    value: int | None = None
    for reading in wellness.resting_hr:
        current = reading.current_day_resting_hr or reading.resting_hr
        if current:
            value = current
    return value
