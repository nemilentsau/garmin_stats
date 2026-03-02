"""
Aggregation and flattening — consumes typed parser output, produces API responses.
No FIT file knowledge here.
"""

from collections.abc import Sequence

import numpy as np

from .models import (
    ActivityReading,
    BodyBatteryReading,
    DailyAggregatesResponse,
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvResponse,
    HRZoneBucket,
    PeriodHeartRateStats,
    PeriodHrvStats,
    PeriodMetricStats,
    PeriodSkinTempStats,
    PeriodSpo2Stats,
    PeriodSummary,
    RespirationReading,
    RestingHRReading,
    SkinTempResponse,
    SleepResponse,
    SpO2Reading,
    StepsReading,
    StressReading,
    WellnessResponse,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# HR zone definitions: (label, lower_bound_inclusive, upper_bound_exclusive_or_None)
HR_ZONE_THRESHOLDS: list[tuple[str, int, int | None]] = [
    ("Rest", 0, 60),
    ("Light", 60, 100),
    ("Moderate", 100, 130),
    ("Vigorous", 130, None),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def safe_avg(values: Sequence[int | float]) -> float | None:
    """Average with rounding, or None if empty."""
    return round(float(np.mean(values)), 1) if values else None


def safe_median(values: Sequence[int | float]) -> float | None:
    """Median, or None if empty."""
    return round(float(np.median(values)), 1) if values else None


def safe_percentile(values: Sequence[int | float], pct: float) -> float | None:
    """Percentile (linear interpolation), or None if empty."""
    return round(float(np.percentile(values, pct)), 1) if values else None


# ---------------------------------------------------------------------------
# Response flattening (per-day lists → flat API responses)
# ---------------------------------------------------------------------------

def flatten_wellness(days: list[DayWellness]) -> WellnessResponse:
    dates: list[str] = []
    heart_rate: list[HeartRateReading] = []
    stress: list[StressReading] = []
    body_battery: list[BodyBatteryReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps_summary: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []
    for d in days:
        dates.append(d.date)
        heart_rate.extend(d.heart_rate)
        stress.extend(d.stress)
        body_battery.extend(d.body_battery)
        spo2.extend(d.spo2)
        respiration.extend(d.respiration)
        activity.extend(d.activity)
        steps_summary.extend(d.steps_summary)
        resting_hr.extend(d.resting_hr)
    return WellnessResponse(
        days=dates, heart_rate=heart_rate, stress=stress,
        body_battery=body_battery, spo2=spo2, respiration=respiration,
        activity=activity, steps_summary=steps_summary, resting_hr=resting_hr,
    )


def flatten_sleep(days: list[DaySleep]) -> SleepResponse:
    return SleepResponse(
        days=[d.date for d in days],
        sleep_levels=[r for d in days for r in d.sleep_levels],
        sleep_assessments=[r for d in days for r in d.sleep_assessments],
    )


def flatten_hrv(days: list[DayHrv]) -> HrvResponse:
    return HrvResponse(
        days=[d.date for d in days],
        hrv_values=[r for d in days for r in d.hrv_values],
        hrv_summaries=[r for d in days for r in d.hrv_summaries],
    )


def flatten_skin_temp(days: list[DaySkinTemp]) -> SkinTempResponse:
    return SkinTempResponse(
        days=[d.date for d in days],
        skin_temp_overnight=[r for d in days for r in d.skin_temp_overnight],
    )


# ---------------------------------------------------------------------------
# Daily aggregation
# ---------------------------------------------------------------------------

def aggregate_day(day: DayData) -> DailyMetric:
    """Compute aggregate stats for a single day."""
    w = day.wellness

    hr_vals = [r.value for r in w.heart_rate]
    stress_vals = [r.value for r in w.stress]
    bb_vals = [r.value for r in w.body_battery]
    spo2_vals = [r.value for r in w.spo2]
    resp_vals = [r.value for r in w.respiration]

    # Last resting HR value for the day
    resting_val: int | None = None
    for r in w.resting_hr:
        v = r.current_day_resting_hr or r.resting_hr
        if v:
            resting_val = v

    # Sleep: take first assessment for the day
    sleep_a = day.sleep.sleep_assessments[0] if day.sleep.sleep_assessments else None

    # HRV: take first summary for the day
    hrv_s = day.hrv.hrv_summaries[0] if day.hrv.hrv_summaries else None

    # Skin temp: take first overnight reading for the day
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
            min=round(min(resp_vals), 1) if resp_vals else None,
            max=round(max(resp_vals), 1) if resp_vals else None,
            median=safe_median(resp_vals),
            q1=safe_percentile(resp_vals, 25),
            q3=safe_percentile(resp_vals, 75),
        ),
        hrv=DailyHrvStats(
            weekly_avg=hrv_s.weekly_average if hrv_s else None,
            nightly_avg=hrv_s.last_night_average if hrv_s else None,
            status=hrv_s.status if hrv_s else None,
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


def compute_period_summary(days: list[DayData]) -> PeriodSummary:
    """Compute period-level stats from raw per-day data (not from daily averages)."""
    # Collect all raw readings across the entire period
    all_hr = [r.value for d in days for r in d.wellness.heart_rate]
    all_stress = [r.value for d in days for r in d.wellness.stress]
    all_resp = [r.value for d in days for r in d.wellness.respiration]

    # Resting HR: collect last non-null per day, then average those
    resting_vals: list[int] = []
    for d in days:
        val = None
        for r in d.wellness.resting_hr:
            v = r.current_day_resting_hr or r.resting_hr
            if v:
                val = v
        if val is not None:
            resting_vals.append(val)

    # HRV: collect from summaries (one per day)
    hrv_nightlys: list[float] = []
    hrv_weeklys: list[float] = []
    hrv_statuses: list[str] = []
    for d in days:
        if d.hrv.hrv_summaries:
            s = d.hrv.hrv_summaries[0]
            if s.last_night_average is not None:
                hrv_nightlys.append(s.last_night_average)
            if s.weekly_average is not None:
                hrv_weeklys.append(s.weekly_average)
            if s.status:
                hrv_statuses.append(s.status)

    # SpO2: collect raw readings + per-day mins for "lowest" and "low days"
    all_spo2 = [r.value for d in days for r in d.wellness.spo2]
    spo2_day_mins: list[int] = []
    for d in days:
        vals = [r.value for r in d.wellness.spo2]
        if vals:
            spo2_day_mins.append(min(vals))

    # Skin temp: collect from overnight readings
    skin_devs: list[float] = []
    skin_nightlys: list[float] = []
    for d in days:
        for r in d.skin_temp.skin_temp_overnight:
            if r.average_deviation is not None:
                skin_devs.append(r.average_deviation)
            if r.nightly_value is not None:
                skin_nightlys.append(r.nightly_value)

    balanced = sum(1 for s in hrv_statuses if "balanced" in s.lower())

    return PeriodSummary(
        heart_rate=PeriodHeartRateStats(
            avg=safe_avg(all_hr),
            avg_resting=safe_avg(resting_vals),
            typical_low=safe_percentile(all_hr, 25),
            typical_high=safe_percentile(all_hr, 75),
            zones=compute_hr_zones(all_hr),
        ),
        stress=PeriodMetricStats(
            avg=safe_avg(all_stress),
            typical_low=safe_percentile(all_stress, 25),
            typical_high=safe_percentile(all_stress, 75),
        ),
        respiration=PeriodMetricStats(
            avg=safe_avg(all_resp),
            typical_low=safe_percentile(all_resp, 25),
            typical_high=safe_percentile(all_resp, 75),
        ),
        hrv=PeriodHrvStats(
            avg_nightly=safe_avg(hrv_nightlys),
            avg_weekly=safe_avg(hrv_weeklys),
            balanced_pct=round(balanced / len(hrv_statuses) * 100) if hrv_statuses else None,
            total_days=len(hrv_statuses),
        ),
        spo2=PeriodSpo2Stats(
            avg=safe_avg(all_spo2),
            lowest_min=float(min(spo2_day_mins)) if spo2_day_mins else None,
            low_days=sum(1 for m in spo2_day_mins if m < 90),
            total_days=len(spo2_day_mins),
        ),
        skin_temp=PeriodSkinTempStats(
            avg_deviation=safe_avg(skin_devs),
            max_deviation=round(max(skin_devs), 2) if skin_devs else None,
            min_deviation=round(min(skin_devs), 2) if skin_devs else None,
            avg_nightly=safe_avg(skin_nightlys),
            days_tracked=len(skin_devs),
        ),
    )


def compute_daily_aggregates(days: list[DayData]) -> DailyAggregatesResponse:
    """Compute daily aggregates for all days."""
    return DailyAggregatesResponse(
        days=[d.date for d in days],
        daily=[aggregate_day(d) for d in days],
        period=compute_period_summary(days),
    )
