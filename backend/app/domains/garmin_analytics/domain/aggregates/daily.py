"""Daily aggregate read-model construction for Garmin analytics."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import (
    DailyAggregatesResponse,
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayData,
    HRZoneBucket,
)
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_max,
    safe_median,
    safe_min,
    safe_percentile,
)

# HR zone definitions: (label, lower_bound_inclusive, upper_bound_exclusive_or_None)
HR_ZONE_THRESHOLDS: list[tuple[str, int, int | None]] = [
    ("Rest", 0, 60),
    ("Light", 60, 100),
    ("Moderate", 100, 130),
    ("Vigorous", 130, None),
]


def normalize_hrv_status(raw: str | None) -> str:
    """Normalize Garmin HRV status strings to clean labels."""
    if not raw:
        return "Unknown"
    value = raw.lower()
    if value == "none":
        return "Unknown"
    # "unbalanced" check must precede "balanced" since the latter is a substring.
    if "unbalanced" in value:
        return "Unbalanced"
    if "balanced" in value:
        return "Balanced"
    if "low" in value:
        return "Low"
    if "high" in value:
        return "High"
    return raw.title()


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


def aggregate_day(day: DayData) -> DailyMetric:
    """Compute aggregate stats for a single day."""
    w = day.wellness

    hr_vals = [r.value for r in w.heart_rate if r.value > 0]
    stress_vals = [r.value for r in w.stress]
    bb_vals = [r.value for r in w.body_battery]
    spo2_vals = [r.value for r in w.spo2]
    resp_vals = [r.value for r in w.respiration]

    resting_val: int | None = None
    for r in w.resting_hr:
        v = r.current_day_resting_hr or r.resting_hr
        if v:
            resting_val = v

    sleep_a = day.sleep.sleep_assessments[0] if day.sleep.sleep_assessments else None
    hrv_s = day.hrv.hrv_summaries[0] if day.hrv.hrv_summaries else None
    skin_t = day.skin_temp.skin_temp_overnight[0] if day.skin_temp.skin_temp_overnight else None

    return DailyMetric(
        date=day.date,
        utc_offset_hours=day.utc_offset_hours,
        heart_rate=DailyHeartRateStats(
            avg=safe_avg(hr_vals),
            min=min(hr_vals) if hr_vals else None,
            max=max(hr_vals) if hr_vals else None,
            median=safe_median(hr_vals),
            q1=safe_percentile(hr_vals, 25),
            q3=safe_percentile(hr_vals, 75),
            resting=resting_val,
            zones=compute_hr_zones(hr_vals),
        ),
        stress=DailyMetricStats(
            avg=safe_avg(stress_vals),
            min=min(stress_vals) if stress_vals else None,
            max=max(stress_vals) if stress_vals else None,
            median=safe_median(stress_vals),
            q1=safe_percentile(stress_vals, 25),
            q3=safe_percentile(stress_vals, 75),
        ),
        body_battery=DailyBodyBatteryStats(
            avg=safe_avg(bb_vals),
            min=min(bb_vals) if bb_vals else None,
            max=max(bb_vals) if bb_vals else None,
            median=safe_median(bb_vals),
            q1=safe_percentile(bb_vals, 25),
            q3=safe_percentile(bb_vals, 75),
        ),
        spo2=DailyMetricStats(
            avg=safe_avg(spo2_vals),
            min=min(spo2_vals) if spo2_vals else None,
            max=max(spo2_vals) if spo2_vals else None,
            median=safe_median(spo2_vals),
            q1=safe_percentile(spo2_vals, 25),
            q3=safe_percentile(spo2_vals, 75),
        ),
        respiration=DailyMetricStats(
            avg=safe_avg(resp_vals),
            min=safe_min(resp_vals),
            max=safe_max(resp_vals),
            median=safe_median(resp_vals),
            q1=safe_percentile(resp_vals, 25),
            q3=safe_percentile(resp_vals, 75),
        ),
        hrv=DailyHrvStats(
            weekly_avg=hrv_s.weekly_average if hrv_s else None,
            nightly_avg=hrv_s.last_night_average if hrv_s else None,
            status=normalize_hrv_status(hrv_s.status) if hrv_s else None,
        ),
        sleep=DailySleepStats(
            score=sleep_a.overall_score if sleep_a else None,
            deep_score=sleep_a.deep_sleep_score if sleep_a else None,
            rem_score=sleep_a.rem_sleep_score if sleep_a else None,
        ),
        skin_temp=DailySkinTempStats(
            deviation=skin_t.average_deviation if skin_t else None,
            deviation_7_day=skin_t.average_7_day_deviation if skin_t else None,
            nightly_value=skin_t.nightly_value if skin_t else None,
        ),
    )


def compute_daily_aggregates(days: list[DayData]) -> DailyAggregatesResponse:
    """Compute daily aggregates for all days."""
    return DailyAggregatesResponse(
        days=[d.date for d in days],
        daily=[aggregate_day(d) for d in days],
    )
