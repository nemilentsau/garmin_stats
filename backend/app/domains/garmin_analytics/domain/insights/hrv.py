"""HRV insight calculations for Garmin analytics."""

from collections import Counter

import numpy as np

from app.domains.garmin_analytics.contracts import (
    HrvDataQuality,
    HrvInsightsResponse,
    HrvIntradaySegment,
    HrvLongBaseline,
    HrvRecovery,
    HrvStatusBucket,
    HrvStreak,
    HrvTrendBand,
)
from app.domains.garmin_analytics.domain.analysis import hrv_patterns
from app.domains.garmin_analytics.domain.insights.hrv_rules import (
    InsightContext,
    build_hrv_insights,
)
from app.domains.garmin_analytics.domain.primitives.timestamps import (
    summarize_timestamp_coverage,
)
from app.domains.garmin_analytics.domain.primitives.trends import prior_7d_avg
from app.domains.garmin_health.contracts import (
    DailyMetric,
    DayHrv,
    HrvValue,
)
from app.domains.garmin_health.domain.daily_metrics import (
    classify_hrv_recovery,
    normalize_hrv_status,
)
from app.utils.numeric import (
    optional_float,
    safe_avg,
    safe_max,
    safe_min,
)

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
    return HrvRecovery(
        baseline_nightly_7d=baseline,
        delta_nightly_from_baseline=delta,
        acute_gap_vs_weekly=acute_gap,
        status=classify_hrv_recovery(delta=delta, status=selected.status),
    )


def _compute_quality(hrv_values: list[HrvValue]) -> HrvDataQuality:
    coverage = summarize_timestamp_coverage([value.timestamp for value in hrv_values])
    return HrvDataQuality(
        sample_count=coverage.sample_count,
        coverage_start=coverage.coverage_start,
        coverage_end=coverage.coverage_end,
        coverage_hours=coverage.coverage_hours,
    )


def _build_intraday_segment(
    *,
    key: str,
    label: str,
    values: list[HrvValue],
) -> HrvIntradaySegment:
    values = sorted(values, key=lambda v: v.timestamp or "")
    coverage = summarize_timestamp_coverage([value.timestamp for value in values])
    sample_values = [value.value for value in values]
    stdev = (
        round(float(np.std(sample_values, ddof=1)), 1)
        if len(sample_values) >= 2 else None
    )

    return HrvIntradaySegment(
        key=key,
        label=label,
        sample_count=coverage.sample_count,
        avg=safe_avg(sample_values),
        min=safe_min(sample_values),
        max=safe_max(sample_values),
        stdev=stdev,
        coverage_start=coverage.coverage_start,
        coverage_end=coverage.coverage_end,
        coverage_hours=coverage.coverage_hours,
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
    baseline_30d = safe_avg(nightly_vals)
    delta = (
        round(baseline_7d - baseline_30d, 1)
        if baseline_7d is not None and baseline_30d is not None else None
    )
    return HrvLongBaseline(baseline_30d=baseline_30d, delta_7d_vs_30d=delta)


def _resting_delta_vs_recent(metrics: list[DailyMetric], selected_index: int) -> float | None:
    selected_resting = metrics[selected_index].heart_rate.resting
    baseline = prior_7d_avg(
        metrics,
        selected_index,
        lambda m: optional_float(m.heart_rate.resting),
    )
    if selected_resting is None or baseline is None:
        return None
    return round(selected_resting - baseline, 1)


def compute_hrv_insights(
    metrics: list[DailyMetric],
    selected_date: str,
    day_rows: list[DayHrv],
) -> HrvInsightsResponse:
    """Compute selected-day HRV insights from daily metrics and raw rows."""
    selected_index = next(
        (i for i, metric in enumerate(metrics) if metric.date == selected_date),
        None,
    )
    if selected_index is None:
        raise LookupError(f"Day {selected_date} not found")

    selected_metric = metrics[selected_index]
    day_values = [value for row in day_rows for value in row.hrv_values]
    recovery = _compute_recovery(metrics, selected_index)
    quality = _compute_quality(day_values)
    overnight_segment = _build_intraday_segment(
        key="all", label="Overnight HRV", values=day_values,
    )
    overnight_stdev = overnight_segment.stdev
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    trend_band = _compute_trend_band(nightly_vals)
    streak = _compute_streak(metrics, selected_index)
    long_baseline = _compute_long_baseline(
        metrics, selected_index, recovery.baseline_nightly_7d,
    )
    baseline_bands = hrv_patterns.extract_baseline_bands(day_rows)
    distribution = hrv_patterns.compute_hrv_distribution(
        nightly_vals, selected_metric.hrv.nightly_avg,
    )
    trajectory = hrv_patterns.compute_trajectory(day_values)
    status_mix = _compute_status_mix(metrics, selected_index)
    day_of_week = hrv_patterns.compute_day_of_week(metrics)
    resting_delta = _resting_delta_vs_recent(metrics, selected_index)
    insights = build_hrv_insights(InsightContext(
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
        intraday_segments=[overnight_segment],
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
