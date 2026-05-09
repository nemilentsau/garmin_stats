"""HRV analysis calculations for Garmin analytics."""

from datetime import datetime

from app.domains.garmin_analytics.contracts import (
    HrvAnalysisResponse,
    HrvBaselineBands,
    HrvDayOfWeekBucket,
    HrvDistribution,
    HrvDistributionBin,
    HrvPatternWindow,
    HrvTrajectory,
    NightlyHrvTrendPoint,
    WeeklyHrvBox,
)
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    weekly_five_number_summaries,
)
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
from app.domains.garmin_health.contracts import (
    DailyMetric,
    DayHrv,
    HrvValue,
)
from app.domains.garmin_health.domain.daily_metrics.hrv import (
    classify_hrv_recovery as _classify_hrv_recovery,
)
from app.utils.numeric import (
    histogram_bins,
    percentile_rank,
    safe_avg,
)
from app.utils.timeutil import parse_iso as _parse_iso

_HRV_DIST_MIN_DAYS = 7
_HRV_BIN_WIDTH = 5
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def classify_hrv_recovery(*, delta: float | None, status: str | None) -> str | None:
    """Compatibility export for shared HRV recovery status classification."""
    return _classify_hrv_recovery(delta=delta, status=status)


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

    bins = [
        HrvDistributionBin(
            bin_start=float(b.bin_start),
            bin_end=float(b.bin_end),
            count=b.count,
        )
        for b in histogram_bins(nightly_vals, _HRV_BIN_WIDTH)
    ]
    selected_percentile = (
        percentile_rank(nightly_vals, selected_value)
        if selected_value is not None else None
    )

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
    summaries = weekly_five_number_summaries(metrics, lambda m: m.hrv.nightly_avg)
    return [
        WeeklyHrvBox(
            iso_week=summary.iso_week,
            min_ms=summary.min,
            q1_ms=summary.q1,
            median_ms=summary.median,
            q3_ms=summary.q3,
            max_ms=summary.max,
            day_count=summary.count,
        )
        for summary in summaries
    ]


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
