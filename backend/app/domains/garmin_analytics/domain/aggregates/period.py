"""Period aggregate read-model construction for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    DayData,
    PeriodBodyBatteryStats,
    PeriodHeartRateStats,
    PeriodHrvStats,
    PeriodMetricStats,
    PeriodSkinTempStats,
    PeriodSleepStats,
    PeriodSpo2Stats,
    PeriodSummary,
)
from app.domains.garmin_analytics.domain.aggregates.daily import compute_hr_zones
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_percentile,
)


def compute_period_heart_rate(days: list[DayData]) -> PeriodHeartRateStats:
    all_hr = [r.value for d in days for r in d.wellness.heart_rate if r.value > 0]
    resting_vals: list[int] = []
    for d in days:
        val = None
        for r in d.wellness.resting_hr:
            v = r.current_day_resting_hr or r.resting_hr
            if v:
                val = v
        if val is not None:
            resting_vals.append(val)

    return PeriodHeartRateStats(
        avg=safe_avg(all_hr),
        avg_resting=safe_avg(resting_vals),
        typical_low=safe_percentile(all_hr, 25),
        typical_high=safe_percentile(all_hr, 75),
        zones=compute_hr_zones(all_hr),
    )


def compute_period_stress(days: list[DayData]) -> PeriodMetricStats:
    all_stress = [r.value for d in days for r in d.wellness.stress]
    return PeriodMetricStats(
        avg=safe_avg(all_stress),
        typical_low=safe_percentile(all_stress, 25),
        typical_high=safe_percentile(all_stress, 75),
    )


def compute_period_respiration(days: list[DayData]) -> PeriodMetricStats:
    all_resp = [r.value for d in days for r in d.wellness.respiration]
    return PeriodMetricStats(
        avg=safe_avg(all_resp),
        typical_low=safe_percentile(all_resp, 25),
        typical_high=safe_percentile(all_resp, 75),
    )


def compute_period_hrv(days: list[DayData]) -> PeriodHrvStats:
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

    balanced = sum(1 for s in hrv_statuses if "balanced" in s.lower())
    return PeriodHrvStats(
        avg_nightly=safe_avg(hrv_nightlys),
        avg_weekly=safe_avg(hrv_weeklys),
        balanced_pct=round(balanced / len(hrv_statuses) * 100)
        if hrv_statuses
        else None,
        total_days=len(hrv_statuses),
    )


def compute_period_spo2(days: list[DayData]) -> PeriodSpo2Stats:
    all_spo2 = [r.value for d in days for r in d.wellness.spo2]
    spo2_day_mins: list[int] = []
    for d in days:
        vals = [r.value for r in d.wellness.spo2]
        if vals:
            spo2_day_mins.append(min(vals))

    return PeriodSpo2Stats(
        avg=safe_avg(all_spo2),
        lowest_min=float(min(spo2_day_mins)) if spo2_day_mins else None,
        low_days=sum(1 for m in spo2_day_mins if m < 90),
        total_days=len(spo2_day_mins),
    )


def compute_period_skin_temp(days: list[DayData]) -> PeriodSkinTempStats:
    skin_devs: list[float] = []
    skin_nightlys: list[float] = []
    for d in days:
        for r in d.skin_temp.skin_temp_overnight:
            if r.average_deviation is not None:
                skin_devs.append(r.average_deviation)
            if r.nightly_value is not None:
                skin_nightlys.append(r.nightly_value)

    return PeriodSkinTempStats(
        avg_deviation=safe_avg(skin_devs),
        max_deviation=round(max(skin_devs), 2) if skin_devs else None,
        min_deviation=round(min(skin_devs), 2) if skin_devs else None,
        avg_nightly=safe_avg(skin_nightlys),
        days_tracked=len(skin_devs),
    )


def compute_period_sleep(days: list[DayData]) -> PeriodSleepStats:
    sleep_scores: list[float] = []
    deep_scores: list[float] = []
    for d in days:
        for a in d.sleep.sleep_assessments:
            if a.overall_score is not None:
                sleep_scores.append(a.overall_score)
            if a.deep_sleep_score is not None:
                deep_scores.append(a.deep_sleep_score)

    return PeriodSleepStats(
        avg_score=safe_avg(sleep_scores),
        avg_deep_score=safe_avg(deep_scores),
        days_tracked=len(sleep_scores),
    )


def compute_period_body_battery(days: list[DayData]) -> PeriodBodyBatteryStats:
    bb_mins: list[float] = []
    bb_maxes: list[float] = []
    for d in days:
        vals = [r.value for r in d.wellness.body_battery]
        if vals:
            bb_mins.append(min(vals))
            bb_maxes.append(max(vals))

    return PeriodBodyBatteryStats(
        avg_min=safe_avg(bb_mins),
        avg_max=safe_avg(bb_maxes),
        days_tracked=len(bb_mins),
    )


def compute_period_summary(days: list[DayData]) -> PeriodSummary:
    """Compute period-level stats from raw per-day data (not from daily averages)."""
    return PeriodSummary(
        heart_rate=compute_period_heart_rate(days),
        stress=compute_period_stress(days),
        respiration=compute_period_respiration(days),
        hrv=compute_period_hrv(days),
        spo2=compute_period_spo2(days),
        skin_temp=compute_period_skin_temp(days),
        sleep=compute_period_sleep(days),
        body_battery=compute_period_body_battery(days),
    )
