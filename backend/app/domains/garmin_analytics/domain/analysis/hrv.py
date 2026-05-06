"""HRV analysis calculations for Garmin analytics."""

from datetime import datetime

import numpy as np

from app.domains.garmin_analytics.domain.primitives.numeric import safe_avg, safe_percentile
from app.domains.garmin_analytics.domain.primitives.trends import (
    group_by_iso_week,
    trailing_ma7,
)
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
from app.models import (
    DailyMetric,
    DayHrv,
    HrvAnalysisResponse,
    HrvBaselineBands,
    HrvDayOfWeekBucket,
    HrvDistribution,
    HrvDistributionBin,
    HrvPatternWindow,
    HrvTrajectory,
    HrvValue,
    NightlyHrvTrendPoint,
    WeeklyHrvBox,
)
from app.utils.timeutil import parse_iso as _parse_iso

_HRV_DIST_MIN_DAYS = 7
_HRV_BIN_WIDTH = 5
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def extract_baseline_bands(day_rows: list[DayHrv]) -> HrvBaselineBands | None:
    """Extract Garmin baseline bands from the first HRV summary of the day."""
    for row in day_rows:
        for summary in row.hrv_summaries:
            fields = (
                summary.baseline_low_upper,
                summary.baseline_balanced_lower,
                summary.baseline_balanced_upper,
                summary.last_night_5_min_high,
            )
            if any(f is not None for f in fields):
                return HrvBaselineBands(
                    baseline_low_upper=summary.baseline_low_upper,
                    baseline_balanced_lower=summary.baseline_balanced_lower,
                    baseline_balanced_upper=summary.baseline_balanced_upper,
                    five_min_high=summary.last_night_5_min_high,
                )
    return None


def compute_hrv_distribution(
    nightly_vals: list[float],
    selected_value: float | None,
) -> HrvDistribution | None:
    """5ms-wide histogram of nightly HRV across the full period."""
    if len(nightly_vals) < _HRV_DIST_MIN_DAYS:
        return None

    min_val = min(nightly_vals)
    max_val = max(nightly_vals)
    bin_start = int(min_val // _HRV_BIN_WIDTH) * _HRV_BIN_WIDTH
    bin_end = (int(max_val // _HRV_BIN_WIDTH) + 1) * _HRV_BIN_WIDTH

    counts: dict[int, int] = {}
    for v in nightly_vals:
        b = int(v // _HRV_BIN_WIDTH) * _HRV_BIN_WIDTH
        counts[b] = counts.get(b, 0) + 1

    bins: list[HrvDistributionBin] = []
    for b in range(bin_start, bin_end, _HRV_BIN_WIDTH):
        c = counts.get(b, 0)
        if c > 0:
            bins.append(HrvDistributionBin(
                bin_start=float(b),
                bin_end=float(b + _HRV_BIN_WIDTH),
                count=c,
            ))

    selected_percentile: float | None = None
    if selected_value is not None:
        arr = np.sort(nightly_vals)
        idx = float(np.searchsorted(arr, selected_value, side="right"))
        selected_percentile = round(idx / len(nightly_vals) * 100, 1)

    return HrvDistribution(
        bins=bins,
        total_days=len(nightly_vals),
        selected_value=selected_value,
        selected_percentile=selected_percentile,
    )


def compute_trajectory(hrv_values: list[HrvValue]) -> HrvTrajectory | None:
    """Split overnight readings into 3 equal time segments and compare averages."""
    parsed = sorted(
        (dt, v.value)
        for v in hrv_values
        if (dt := _parse_iso(v.timestamp)) is not None
    )
    if len(parsed) < 6:
        return None

    t_start = parsed[0][0]
    t_end = parsed[-1][0]
    span = (t_end - t_start).total_seconds()
    if span <= 0:
        return None
    third = span / 3
    t_mid_start = t_start.timestamp() + third
    t_late_start = t_start.timestamp() + 2 * third

    early: list[float] = []
    mid: list[float] = []
    late: list[float] = []
    for dt, val in parsed:
        ts = dt.timestamp()
        if ts < t_mid_start:
            early.append(val)
        elif ts < t_late_start:
            mid.append(val)
        else:
            late.append(val)

    if not early or not mid or not late:
        return None

    early_avg = safe_avg(early)
    mid_avg = safe_avg(mid)
    late_avg = safe_avg(late)
    if early_avg is None or mid_avg is None or late_avg is None:
        return None

    diff = late_avg - early_avg
    if diff > 5:
        direction = "rising"
    elif diff < -5:
        direction = "falling"
    else:
        direction = "flat"

    return HrvTrajectory(
        early_avg=early_avg,
        mid_avg=mid_avg,
        late_avg=late_avg,
        direction=direction,
    )


def compute_day_of_week(metrics: list[DailyMetric]) -> list[HrvDayOfWeekBucket]:
    """Average nightly HRV grouped by weekday across the full dataset."""
    groups: dict[int, list[float]] = {i: [] for i in range(7)}
    for m in metrics:
        if m.hrv.nightly_avg is not None:
            try:
                weekday = datetime.strptime(m.date, "%Y-%m-%d").weekday()
            except ValueError:
                continue
            groups[weekday].append(m.hrv.nightly_avg)

    return [
        HrvDayOfWeekBucket(
            day=_DAY_NAMES[i],
            day_index=i,
            avg_nightly=safe_avg(vals),
            sample_count=len(vals),
        )
        for i, vals in sorted(groups.items())
    ]


def compute_nightly_hrv_trend(
    metrics: list[DailyMetric],
) -> list[NightlyHrvTrendPoint]:
    """Raw nightly HRV + 7-day trailing moving average."""
    nightly_values: list[float | None] = [m.hrv.nightly_avg for m in metrics]
    ma7_values = trailing_ma7(nightly_values)

    return [
        NightlyHrvTrendPoint(
            date=m.date,
            nightly_avg=nightly_values[i],
            ma7=ma7_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def compute_weekly_hrv_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyHrvBox]:
    """Group nightly HRV by ISO week, compute 5-number summary."""
    weeks = group_by_iso_week(metrics, lambda m: m.hrv.nightly_avg)
    result: list[WeeklyHrvBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        result.append(
            WeeklyHrvBox(
                iso_week=week_key,
                min_ms=float(vals[0]),
                q1_ms=safe_percentile(vals, 25),
                median_ms=safe_percentile(vals, 50),
                q3_ms=safe_percentile(vals, 75),
                max_ms=float(vals[-1]),
                day_count=len(vals),
            )
        )
    return result


def compute_pattern_window(
    metrics: list[DailyMetric],
    selected_nightly: float | None,
) -> HrvPatternWindow:
    """Distribution + day-of-week stats for a given slice of metrics."""
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    return HrvPatternWindow(
        distribution=compute_hrv_distribution(nightly_vals, selected_nightly),
        day_of_week=compute_day_of_week(metrics),
    )


def compute_pattern_windows(
    metrics: list[DailyMetric],
    selected_nightly: float | None,
) -> dict[str, HrvPatternWindow]:
    """Pre-compute pattern stats for each time window."""
    return compute_windows(
        metrics,
        lambda subset: compute_pattern_window(subset, selected_nightly),
    )


def compute_hrv_analysis(metrics: list[DailyMetric]) -> HrvAnalysisResponse:
    selected_nightly: float | None = None
    if metrics and metrics[-1].hrv.nightly_avg is not None:
        selected_nightly = metrics[-1].hrv.nightly_avg
    return HrvAnalysisResponse(
        nightly_trend=compute_nightly_hrv_trend(metrics),
        weekly_boxplots=compute_weekly_hrv_boxplots(metrics),
        pattern_windows=compute_pattern_windows(metrics, selected_nightly),
    )
