"""
Aggregation and flattening — consumes typed parser output, produces API responses.
No FIT file knowledge here.
"""

import numpy as np

from .models import (
    DayWellness,
    DaySleep,
    DayHrv,
    DaySkinTemp,
    DayData,
    WellnessResponse,
    SleepResponse,
    HrvResponse,
    SkinTempResponse,
    DailyHeartRateStats,
    DailyMetricStats,
    DailyBodyBatteryStats,
    DailyHrvStats,
    DailySleepStats,
    DailySkinTempStats,
    DailyMetric,
    DailyAggregatesResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_avg(values: list[int | float]) -> float | None:
    """Average with rounding, or None if empty."""
    return round(float(np.mean(values)), 1) if values else None


def safe_median(values: list[int | float]) -> float | None:
    """Median, or None if empty."""
    return round(float(np.median(values)), 1) if values else None


def safe_percentile(values: list[int | float], pct: float) -> float | None:
    """Percentile (linear interpolation), or None if empty."""
    return round(float(np.percentile(values, pct)), 1) if values else None


# ---------------------------------------------------------------------------
# Response flattening (per-day lists → flat API responses)
# ---------------------------------------------------------------------------

def flatten_wellness(days: list[DayWellness]) -> WellnessResponse:
    return WellnessResponse(
        days=[d.date for d in days],
        heart_rate=[r for d in days for r in d.heart_rate],
        stress=[r for d in days for r in d.stress],
        body_battery=[r for d in days for r in d.body_battery],
        spo2=[r for d in days for r in d.spo2],
        respiration=[r for d in days for r in d.respiration],
        activity=[r for d in days for r in d.activity],
        steps_summary=[r for d in days for r in d.steps_summary],
        resting_hr=[r for d in days for r in d.resting_hr],
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
        heart_rate=DailyHeartRateStats(
            avg=safe_avg(hr_vals),
            min=min(hr_vals) if hr_vals else None,
            max=max(hr_vals) if hr_vals else None,
            median=safe_median(hr_vals),
            q1=safe_percentile(hr_vals, 25),
            q3=safe_percentile(hr_vals, 75),
            resting=resting_val,
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


def compute_daily_aggregates(days: list[DayData]) -> DailyAggregatesResponse:
    """Compute daily aggregates for all days."""
    return DailyAggregatesResponse(
        days=[d.date for d in days],
        daily=[aggregate_day(d) for d in days],
    )
