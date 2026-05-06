"""HRV insight calculations for Garmin analytics."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.models import (
    DailyMetric,
    DayHrv,
    HrvBaselineBands,
    HrvDataQuality,
    HrvDayOfWeekBucket,
    HrvDistribution,
    HrvDistributionBin,
    HrvInsight,
    HrvInsightsResponse,
    HrvIntradaySegment,
    HrvLongBaseline,
    HrvRecovery,
    HrvStatusBucket,
    HrvStreak,
    HrvTrajectory,
    HrvTrendBand,
    HrvValue,
)
from app.utils.timeutil import parse_iso as _parse_iso

from .daily_aggregates import normalize_hrv_status
from .trends import prior_7d_avg

_BAD_HRV_STATUSES = {"Low", "Unbalanced"}


def _compute_recovery(metrics: list[DailyMetric], selected_index: int) -> HrvRecovery:
    selected = metrics[selected_index].hrv
    baseline = prior_7d_avg(metrics, selected_index, lambda m: m.hrv.nightly_avg)
    nightly = selected.nightly_avg
    delta = (
        round(nightly - baseline, 1)
        if nightly is not None and baseline is not None else None
    )
    acute_gap = (
        round(nightly - selected.weekly_avg, 1)
        if nightly is not None and selected.weekly_avg is not None else None
    )
    status_text = selected.status.lower() if selected.status else ""
    if delta is None:
        status = None
    elif delta <= -10 or "low" in status_text or "unbalanced" in status_text:
        status = "suppressed"
    elif delta <= -5:
        status = "below_baseline"
    elif delta >= 8:
        status = "elevated"
    else:
        status = "stable"

    return HrvRecovery(
        baseline_nightly_7d=baseline,
        delta_nightly_from_baseline=delta,
        acute_gap_vs_weekly=acute_gap,
        status=status,
    )


def _compute_quality(hrv_values: list[HrvValue]) -> HrvDataQuality:
    parsed_times = sorted(
        dt for dt in (_parse_iso(value.timestamp) for value in hrv_values) if dt is not None
    )
    coverage_start = parsed_times[0].isoformat() if parsed_times else None
    coverage_end = parsed_times[-1].isoformat() if parsed_times else None
    coverage_hours = (
        round((parsed_times[-1] - parsed_times[0]).total_seconds() / 3600, 2)
        if len(parsed_times) >= 2 else None
    )
    return HrvDataQuality(
        sample_count=len(hrv_values),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        coverage_hours=coverage_hours,
    )


def _build_intraday_segment(
    *,
    key: str,
    label: str,
    values: list[HrvValue],
) -> HrvIntradaySegment:
    values = sorted(values, key=lambda v: v.timestamp or "")
    parsed_times = sorted(
        dt for dt in (_parse_iso(value.timestamp) for value in values) if dt is not None
    )
    coverage_start = parsed_times[0].isoformat() if parsed_times else None
    coverage_end = parsed_times[-1].isoformat() if parsed_times else None
    coverage_hours = (
        round((parsed_times[-1] - parsed_times[0]).total_seconds() / 3600, 2)
        if len(parsed_times) >= 2 else None
    )
    sample_values = [value.value for value in values]
    avg = (
        round(sum(sample_values) / len(sample_values), 1)
        if sample_values else None
    )
    min_val = round(min(sample_values), 1) if sample_values else None
    max_val = round(max(sample_values), 1) if sample_values else None
    stdev = (
        round(float(np.std(sample_values, ddof=1)), 1)
        if len(sample_values) >= 2 else None
    )

    return HrvIntradaySegment(
        key=key,
        label=label,
        sample_count=len(values),
        avg=avg,
        min=min_val,
        max=max_val,
        stdev=stdev,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        coverage_hours=coverage_hours,
        values=values,
    )


def _compute_trend_band(nightly_vals: list[float]) -> HrvTrendBand:
    if len(nightly_vals) < 2:
        return HrvTrendBand()
    low = round(float(np.percentile(nightly_vals, 25)), 1)
    high = round(float(np.percentile(nightly_vals, 75)), 1)
    return HrvTrendBand(nightly_typical_low=low, nightly_typical_high=high)


def _compute_status_mix(metrics: list[DailyMetric], selected_index: int) -> list[HrvStatusBucket]:
    window = metrics[max(0, selected_index - 13):selected_index + 1]
    labels = [
        normalize_hrv_status(metric.hrv.status)
        for metric in window
        if metric.hrv.status
    ]
    if not labels:
        return []
    counts = Counter(labels)
    total = sum(counts.values())
    sorted_items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [
        HrvStatusBucket(
            label=label,
            count=count,
            pct=round(count / total * 100, 1),
        )
        for label, count in sorted_items
    ]


def _compute_streak(metrics: list[DailyMetric], selected_index: int) -> HrvStreak:
    current_status = normalize_hrv_status(metrics[selected_index].hrv.status)
    streak_days = 1
    for i in range(selected_index - 1, -1, -1):
        if normalize_hrv_status(metrics[i].hrv.status) == current_status:
            streak_days += 1
        else:
            break

    window_start = max(0, selected_index - 13)
    window = metrics[window_start:selected_index + 1]
    worst = 0
    run = 0
    for metric in window:
        if normalize_hrv_status(metric.hrv.status) in _BAD_HRV_STATUSES:
            run += 1
            worst = max(worst, run)
        else:
            run = 0

    return HrvStreak(
        current_status=current_status,
        streak_days=streak_days,
        worst_recent_streak=worst,
    )


def _compute_long_baseline(
    metrics: list[DailyMetric],
    selected_index: int,
    baseline_7d: float | None,
) -> HrvLongBaseline | None:
    window = metrics[max(0, selected_index - 30):selected_index]
    nightly_vals = [
        m.hrv.nightly_avg for m in window if m.hrv.nightly_avg is not None
    ]
    if len(nightly_vals) < 14:
        return None
    baseline_30d = round(sum(nightly_vals) / len(nightly_vals), 1)
    delta = (
        round(baseline_7d - baseline_30d, 1)
        if baseline_7d is not None else None
    )
    return HrvLongBaseline(baseline_30d=baseline_30d, delta_7d_vs_30d=delta)


def _resting_delta_vs_recent(metrics: list[DailyMetric], selected_index: int) -> float | None:
    selected_resting = metrics[selected_index].heart_rate.resting
    baseline = prior_7d_avg(
        metrics,
        selected_index,
        lambda m: float(m.heart_rate.resting) if m.heart_rate.resting is not None else None,
    )
    if selected_resting is None or baseline is None:
        return None
    return round(selected_resting - baseline, 1)


@dataclass(frozen=True, slots=True)
class _InsightContext:
    selected: DailyMetric
    recovery: HrvRecovery
    quality: HrvDataQuality
    resting_delta: float | None
    overnight_stdev: float | None = None
    streak: HrvStreak | None = None
    long_baseline: HrvLongBaseline | None = None
    trajectory: HrvTrajectory | None = None


def _build_insights(ctx: _InsightContext) -> list[HrvInsight]:
    insights: list[HrvInsight] = []
    status = ctx.recovery.status

    if status == "suppressed":
        insights.append(HrvInsight(
            level="warning",
            title="HRV appears suppressed",
            detail=(
                f"Nightly HRV is {ctx.recovery.delta_nightly_from_baseline:+.1f} ms versus the "
                "prior 7-day baseline."
            )
            if ctx.recovery.delta_nightly_from_baseline is not None
            else "Nightly HRV is below expected levels.",
        ))
    elif status == "below_baseline":
        insights.append(HrvInsight(
            level="caution",
            title="HRV is below baseline",
            detail=(
                f"Nightly HRV is {ctx.recovery.delta_nightly_from_baseline:+.1f} ms versus the "
                "prior 7-day baseline."
            )
            if ctx.recovery.delta_nightly_from_baseline is not None
            else "Nightly HRV is mildly below baseline.",
        ))
    elif status == "elevated":
        insights.append(HrvInsight(
            level="good",
            title="HRV is above baseline",
            detail=(
                f"Nightly HRV is {ctx.recovery.delta_nightly_from_baseline:+.1f} ms versus the "
                "prior 7-day baseline."
            )
            if ctx.recovery.delta_nightly_from_baseline is not None
            else "Nightly HRV is above baseline.",
        ))

    if ctx.recovery.acute_gap_vs_weekly is not None and ctx.recovery.acute_gap_vs_weekly <= -8:
        insights.append(HrvInsight(
            level="caution",
            title="Acute recovery is below weekly trend",
            detail=(
                f"Nightly HRV is {ctx.recovery.acute_gap_vs_weekly:+.1f} ms versus weekly average, "
                "which can indicate short-term strain."
            ),
        ))

    if (
        ctx.overnight_stdev is not None
        and ctx.overnight_stdev > 25
        and status in {"suppressed", "below_baseline"}
    ):
        insights.append(HrvInsight(
            level="caution",
            title="High overnight HRV volatility",
            detail=(
                f"Overnight HRV stdev is {ctx.overnight_stdev:.1f} ms, suggesting irregular "
                "autonomic activity alongside suppressed recovery."
            ),
        ))

    if (
        ctx.streak is not None
        and ctx.streak.current_status in _BAD_HRV_STATUSES
        and ctx.streak.streak_days >= 3
    ):
        insights.append(HrvInsight(
            level="warning",
            title="Extended low HRV streak",
            detail=(
                f"{ctx.streak.streak_days} consecutive days of "
                f"{ctx.streak.current_status} HRV status. "
                "Consider reviewing recent stressors, sleep, or training load."
            ),
        ))

    if (
        ctx.trajectory is not None
        and ctx.trajectory.direction == "falling"
        and status in {"suppressed", "below_baseline"}
    ):
        insights.append(HrvInsight(
            level="warning",
            title="HRV declined through the night",
            detail="HRV declined through the night, suggesting disrupted recovery.",
        ))

    if (
        ctx.long_baseline is not None
        and ctx.long_baseline.delta_7d_vs_30d is not None
        and ctx.long_baseline.delta_7d_vs_30d < -5
    ):
        insights.append(HrvInsight(
            level="caution",
            title="7-day baseline is trending below 30-day average",
            detail=(
                f"Recent 7-day baseline is {ctx.long_baseline.delta_7d_vs_30d:+.1f} ms versus "
                f"30-day average of {ctx.long_baseline.baseline_30d:.1f} ms."
            ),
        ))

    sleep_score = ctx.selected.sleep.score
    if sleep_score is not None and sleep_score < 70 and status in {"suppressed", "below_baseline"}:
        insights.append(HrvInsight(
            level="warning",
            title="Sleep and HRV both indicate reduced recovery",
            detail=f"Sleep score is {sleep_score}, aligning with lower-than-baseline HRV.",
        ))

    if (
        ctx.resting_delta is not None
        and ctx.resting_delta >= 4
        and status in {"suppressed", "below_baseline"}
    ):
        insights.append(HrvInsight(
            level="warning",
            title="Resting HR and HRV are diverging unfavorably",
            detail=(
                f"Resting HR is +{ctx.resting_delta:.1f} bpm versus recent baseline "
                "while HRV is below baseline."
            ),
        ))

    if (
        not insights
        and sleep_score is not None
        and sleep_score >= 80
        and ctx.selected.hrv.status
        and "balanced" in ctx.selected.hrv.status.lower()
    ):
        insights.append(HrvInsight(
            level="good",
            title="HRV recovery signals look stable",
            detail="Balanced HRV status and strong sleep score suggest good recovery.",
        ))

    if ctx.quality.sample_count < 20:
        insights.append(HrvInsight(
            level="info",
            title="Low HRV sample coverage",
            detail=(
                f"Only {ctx.quality.sample_count} intraday HRV values "
                "were available for this day."
            ),
        ))

    return insights


_HRV_DIST_MIN_DAYS = 7
_HRV_BIN_WIDTH = 5


def _extract_baseline_bands(day_rows: list[DayHrv]) -> HrvBaselineBands | None:
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


def _compute_hrv_distribution(
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
                bin_start=float(b), bin_end=float(b + _HRV_BIN_WIDTH), count=c,
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


def _compute_trajectory(hrv_values: list[HrvValue]) -> HrvTrajectory | None:
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

    early_avg = round(sum(early) / len(early), 1)
    mid_avg = round(sum(mid) / len(mid), 1)
    late_avg = round(sum(late) / len(late), 1)

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


_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _compute_day_of_week(metrics: list[DailyMetric]) -> list[HrvDayOfWeekBucket]:
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
            avg_nightly=round(sum(vals) / len(vals), 1) if vals else None,
            sample_count=len(vals),
        )
        for i, vals in sorted(groups.items())
    ]


def load_hrv_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HrvInsightsResponse:
    """Load backend-derived HRV insights for a day (or latest if omitted)."""
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No HRV data available")

    selected_date = date or metrics[-1].date
    selected_index = next(
        (i for i, metric in enumerate(metrics) if metric.date == selected_date),
        None,
    )
    if selected_index is None:
        raise LookupError(f"Day {selected_date} not found")

    selected_metric = metrics[selected_index]
    day_rows = repo.load_hrv(selected_date)
    day_values = [value for row in day_rows for value in row.hrv_values]
    recovery = _compute_recovery(metrics, selected_index)
    quality = _compute_quality(day_values)
    intraday_segments = [
        _build_intraday_segment(key="all", label="Overnight HRV", values=day_values),
    ]
    overnight_stdev = intraday_segments[0].stdev if intraday_segments else None
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    trend_band = _compute_trend_band(nightly_vals)
    streak = _compute_streak(metrics, selected_index)
    long_baseline = _compute_long_baseline(
        metrics, selected_index, recovery.baseline_nightly_7d,
    )
    baseline_bands = _extract_baseline_bands(day_rows)
    distribution = _compute_hrv_distribution(
        nightly_vals, selected_metric.hrv.nightly_avg,
    )
    trajectory = _compute_trajectory(day_values)
    status_mix = _compute_status_mix(metrics, selected_index)
    day_of_week = _compute_day_of_week(metrics)
    resting_delta = _resting_delta_vs_recent(metrics, selected_index)
    insights = _build_insights(_InsightContext(
        selected=selected_metric,
        recovery=recovery,
        quality=quality,
        resting_delta=resting_delta,
        overnight_stdev=overnight_stdev,
        streak=streak,
        long_baseline=long_baseline,
        trajectory=trajectory,
    ))

    return HrvInsightsResponse(
        date=selected_date,
        day_stats=selected_metric.hrv,
        recovery=recovery,
        quality=quality,
        intraday_segments=intraday_segments,
        trend_band=trend_band,
        streak=streak,
        long_baseline=long_baseline,
        baseline_bands=baseline_bands,
        distribution=distribution,
        trajectory=trajectory,
        status_mix=status_mix,
        day_of_week=day_of_week,
        insights=insights,
    )
