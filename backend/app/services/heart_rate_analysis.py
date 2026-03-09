"""Heart-rate analysis: circadian, sleeping HR, resting trend, distribution, boxplots."""

from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime

from ..infra import cache
from ..infra.database import load_daily_metrics, load_sleep, load_wellness
from ..models import (
    CircadianHRPoint,
    DailyAvgHRTrendPoint,
    DailyMetric,
    DaySleep,
    DayWellness,
    HeartRateAnalysisResponse,
    HRDistributionResponse,
    HRHistogramBin,
    HRPatternWindow,
    RestingHRTrendPoint,
    SleepingHRPoint,
    WeeklyRestingHRBox,
)
from ..utils.timeutil import parse_iso as _parse_iso
from ._windows import compute_windows


def _compute_circadian_profile(
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


def _compute_sleeping_hr_trend(
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

        # Sort by timestamp
        parsed_levels: list[tuple[datetime, str]] = []
        for sl in levels:
            dt = _parse_iso(sl.timestamp)
            if dt is not None:
                parsed_levels.append((dt, sl.level))
        if not parsed_levels:
            continue
        parsed_levels.sort(key=lambda x: x[0])

        # Build sorted interval start times for bisect
        interval_starts = [pl[0] for pl in parsed_levels]
        interval_stages = [pl[1] for pl in parsed_levels]

        # Determine which calendar dates the sleep spans
        first_ts = parsed_levels[0][0]
        last_ts = parsed_levels[-1][0]
        dates_needed = {first_ts.strftime("%Y-%m-%d"), last_ts.strftime("%Y-%m-%d")}

        # Collect HR readings from relevant dates
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
                # Must fall within the sleep window
                if hr_dt < first_ts or hr_dt > last_ts:
                    continue
                # Find which sleep interval this reading falls in
                idx = bisect_right(interval_starts, hr_dt) - 1
                if idx < 0:
                    continue
                stage = interval_stages[idx]
                if stage in sleeping_stages:
                    hr_values.append(r.value)

        if hr_values:
            avg = round(sum(hr_values) / len(hr_values), 1)
            result.append(SleepingHRPoint(
                date=sleep_day.date,
                avg_sleeping_bpm=avg,
                sample_count=len(hr_values),
            ))

    # Compute 7-day trailing moving average
    values = [p.avg_sleeping_bpm for p in result]
    for i, point in enumerate(result):
        window_start = max(0, i - 6)
        window = [v for v in values[window_start : i + 1] if v is not None]
        point.ma7_bpm = round(sum(window) / len(window), 1) if window else None

    return result


def _compute_resting_hr_trend(
    metrics: list[DailyMetric],
) -> list[RestingHRTrendPoint]:
    """Raw resting HR + 7-day trailing moving average."""
    points: list[RestingHRTrendPoint] = []
    resting_values: list[int | None] = [m.heart_rate.resting for m in metrics]

    for i, m in enumerate(metrics):
        resting = resting_values[i]
        # 7-day trailing window: i-6 to i inclusive
        window_start = max(0, i - 6)
        window = [v for v in resting_values[window_start:i + 1] if v is not None]
        ma7 = round(sum(window) / len(window), 1) if window else None
        points.append(RestingHRTrendPoint(
            date=m.date,
            resting_bpm=resting,
            ma7_bpm=ma7,
        ))
    return points


def _compute_daily_avg_trend(
    metrics: list[DailyMetric],
) -> list[DailyAvgHRTrendPoint]:
    """Raw daily avg HR + 7-day trailing moving average."""
    points: list[DailyAvgHRTrendPoint] = []
    avg_values: list[float | None] = [m.heart_rate.avg for m in metrics]

    for i, m in enumerate(metrics):
        avg = avg_values[i]
        window_start = max(0, i - 6)
        window = [v for v in avg_values[window_start:i + 1] if v is not None]
        ma7 = round(sum(window) / len(window), 1) if window else None
        points.append(DailyAvgHRTrendPoint(
            date=m.date,
            avg_bpm=avg,
            ma7_bpm=ma7,
        ))
    return points


def _compute_hr_distribution(
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


def _compute_weekly_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyRestingHRBox]:
    """Group resting HR by ISO week, compute 5-number summary."""
    from datetime import date as date_type

    weeks: dict[str, list[int]] = {}
    for m in metrics:
        if m.heart_rate.resting is None:
            continue
        try:
            d = date_type.fromisoformat(m.date)
        except ValueError:
            continue
        iso_year, iso_week, _ = d.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weeks.setdefault(key, []).append(m.heart_rate.resting)

    result: list[WeeklyRestingHRBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        n = len(vals)
        if n == 0:
            continue

        def percentile(data: list[int], pct: float) -> float:
            k = (len(data) - 1) * pct / 100
            f = int(k)
            c = f + 1
            if c >= len(data):
                return float(data[f])
            return round(data[f] + (k - f) * (data[c] - data[f]), 1)

        result.append(WeeklyRestingHRBox(
            iso_week=week_key,
            min_bpm=float(vals[0]),
            q1_bpm=percentile(vals, 25),
            median_bpm=percentile(vals, 50),
            q3_bpm=percentile(vals, 75),
            max_bpm=float(vals[-1]),
            day_count=n,
        ))
    return result


def load_heart_rate_analysis() -> HeartRateAnalysisResponse:
    """Load all wellness + sleep + metrics, compute analysis features (cached)."""
    return cache.cached(cache.HR_ANALYSIS, _compute_heart_rate_analysis)


def _compute_heart_rate_analysis() -> HeartRateAnalysisResponse:
    all_wellness = load_wellness()
    all_sleep = load_sleep()
    metrics = load_daily_metrics()
    pattern_windows = compute_windows(
        all_wellness,
        lambda subset: HRPatternWindow(
            circadian_profile=_compute_circadian_profile(subset),
        ),
    )
    return HeartRateAnalysisResponse(
        sleeping_hr_trend=_compute_sleeping_hr_trend(all_wellness, all_sleep),
        resting_hr_trend=_compute_resting_hr_trend(metrics),
        daily_avg_trend=_compute_daily_avg_trend(metrics),
        weekly_boxplots=_compute_weekly_boxplots(metrics),
        pattern_windows=pattern_windows,
    )


def load_hr_distribution(date: str) -> HRDistributionResponse:
    """Load one day's wellness, build histogram."""
    wellness_days = load_wellness(date)
    if not wellness_days:
        return HRDistributionResponse(date=date, bins=[], sample_count=0)

    readings = [(r.value, r.timestamp) for r in wellness_days[0].heart_rate if r.value > 0]
    bins = _compute_hr_distribution(readings)
    return HRDistributionResponse(
        date=date,
        bins=bins,
        sample_count=len(readings),
    )
