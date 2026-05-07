"""Heart-rate analysis calculations for Garmin analytics."""

from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime

from app.domains.garmin_analytics.contracts import (
    CircadianHRPoint,
    DailyAvgHRTrendPoint,
    DailyMetric,
    DaySleep,
    DayWellness,
    HeartRateAnalysisResponse,
    HRHistogramBin,
    HRPatternWindow,
    RestingHRTrendPoint,
    SleepingHRPoint,
    WeeklyRestingHRBox,
)
from app.domains.garmin_analytics.domain.primitives.numeric import safe_avg
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    weekly_five_number_summaries,
)
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
from app.utils.timeutil import parse_iso as _parse_iso


def compute_circadian_profile(
    wellness_days: list[DayWellness],
) -> list[CircadianHRPoint]:
    """Avg HR by hour 0-23 across all days."""
    sums: list[float] = [0.0] * 24
    counts: list[int] = [0] * 24
    for w in wellness_days:
        for r in w.heart_rate:
            if r.value <= 0:
                continue
            dt = _parse_iso(r.timestamp)
            if dt is None:
                continue
            h = dt.hour
            sums[h] += r.value
            counts[h] += 1
    return [
        CircadianHRPoint(
            hour=h,
            avg_bpm=round(sums[h] / counts[h], 1) if counts[h] > 0 else None,
            sample_count=counts[h],
        )
        for h in range(24)
    ]


def compute_sleeping_hr_trend(
    all_wellness: list[DayWellness],
    all_sleep: list[DaySleep],
) -> list[SleepingHRPoint]:
    """Avg HR during actual sleep stages (light/deep/REM, excluding awake).

    Sleep data for date D (wake-up date) has sleep level timestamps spanning
    evening of D-1 through morning of D.  We correlate with HR from both dates.
    """
    wellness_by_date: dict[str, DayWellness] = {w.date: w for w in all_wellness}
    sleeping_stages = {"light", "deep", "rem"}
    result: list[SleepingHRPoint] = []

    for sleep_day in all_sleep:
        levels = sleep_day.sleep_levels
        if not levels:
            continue

        parsed_levels: list[tuple[datetime, str]] = []
        for sl in levels:
            dt = _parse_iso(sl.timestamp)
            if dt is not None:
                parsed_levels.append((dt, sl.level))
        if not parsed_levels:
            continue
        parsed_levels.sort(key=lambda x: x[0])

        interval_starts = [pl[0] for pl in parsed_levels]
        interval_stages = [pl[1] for pl in parsed_levels]

        first_ts = parsed_levels[0][0]
        last_ts = parsed_levels[-1][0]
        dates_needed = {first_ts.strftime("%Y-%m-%d"), last_ts.strftime("%Y-%m-%d")}

        hr_values: list[int] = []
        for d in dates_needed:
            w = wellness_by_date.get(d)
            if w is None:
                continue
            for r in w.heart_rate:
                if r.value <= 0:
                    continue
                hr_dt = _parse_iso(r.timestamp)
                if hr_dt is None:
                    continue
                if hr_dt < first_ts or hr_dt > last_ts:
                    continue
                idx = bisect_right(interval_starts, hr_dt) - 1
                if idx < 0:
                    continue
                stage = interval_stages[idx]
                if stage in sleeping_stages:
                    hr_values.append(r.value)

        if hr_values:
            result.append(SleepingHRPoint(
                date=sleep_day.date,
                avg_sleeping_bpm=safe_avg(hr_values),
                sample_count=len(hr_values),
            ))

    ma7_values = trailing_ma7([p.avg_sleeping_bpm for p in result])
    for i, point in enumerate(result):
        point.ma7_bpm = ma7_values[i]

    return result


def compute_resting_hr_trend(
    metrics: list[DailyMetric],
) -> list[RestingHRTrendPoint]:
    """Raw resting HR + 7-day trailing moving average."""
    resting_values: list[float | None] = [
        float(m.heart_rate.resting) if m.heart_rate.resting is not None else None
        for m in metrics
    ]
    ma7_values = trailing_ma7(resting_values)

    return [
        RestingHRTrendPoint(
            date=m.date,
            resting_bpm=m.heart_rate.resting,
            ma7_bpm=ma7_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def compute_daily_avg_trend(
    metrics: list[DailyMetric],
) -> list[DailyAvgHRTrendPoint]:
    """Raw daily avg HR + 7-day trailing moving average."""
    avg_values: list[float | None] = [m.heart_rate.avg for m in metrics]
    ma7_values = trailing_ma7(avg_values)

    return [
        DailyAvgHRTrendPoint(
            date=m.date,
            avg_bpm=avg_values[i],
            ma7_bpm=ma7_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def compute_hr_distribution(
    hr_readings: Sequence[tuple[int, str | None]],
    bin_width: int = 5,
) -> list[HRHistogramBin]:
    """5-bpm histogram bins for heart rate readings."""
    if not hr_readings:
        return []
    values = [v for v, _ in hr_readings if v > 0]
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)
    bin_start = (min_val // bin_width) * bin_width
    bin_end = ((max_val // bin_width) + 1) * bin_width

    counts: dict[int, int] = {}
    for v in values:
        b = (v // bin_width) * bin_width
        counts[b] = counts.get(b, 0) + 1

    bins: list[HRHistogramBin] = []
    for b in range(bin_start, bin_end, bin_width):
        c = counts.get(b, 0)
        if c > 0:
            bins.append(HRHistogramBin(bin_start=b, bin_end=b + bin_width, count=c))
    return bins


def compute_weekly_resting_hr_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyRestingHRBox]:
    """Group resting HR by ISO week, compute 5-number summary."""
    summaries = weekly_five_number_summaries(
        metrics,
        lambda m: float(m.heart_rate.resting) if m.heart_rate.resting is not None else None,
    )
    return [
        WeeklyRestingHRBox(
            iso_week=summary.iso_week,
            min_bpm=summary.min,
            q1_bpm=summary.q1,
            median_bpm=summary.median,
            q3_bpm=summary.q3,
            max_bpm=summary.max,
            day_count=summary.count,
        )
        for summary in summaries
    ]


def compute_heart_rate_analysis(
    all_wellness: list[DayWellness],
    all_sleep: list[DaySleep],
    metrics: list[DailyMetric],
) -> HeartRateAnalysisResponse:
    pattern_windows = compute_windows(
        all_wellness,
        lambda subset: HRPatternWindow(
            circadian_profile=compute_circadian_profile(subset),
        ),
    )
    return HeartRateAnalysisResponse(
        sleeping_hr_trend=compute_sleeping_hr_trend(all_wellness, all_sleep),
        resting_hr_trend=compute_resting_hr_trend(metrics),
        daily_avg_trend=compute_daily_avg_trend(metrics),
        weekly_boxplots=compute_weekly_resting_hr_boxplots(metrics),
        pattern_windows=pattern_windows,
    )
