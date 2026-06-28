"""HRV insight calculations for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    HrvBaseline,
    HrvDataQuality,
    HrvInsightsResponse,
    HrvRecovery,
    HrvStreak,
)
from app.domains.garmin_analytics.domain.insights.hrv_rules import (
    InsightContext,
    build_hrv_insights,
)
from app.domains.garmin_analytics.domain.primitives.timestamps import (
    summarize_timestamp_coverage,
)
from app.domains.garmin_analytics.domain.primitives.trends import (
    BASELINE_MIN_DAYS,
    BASELINE_WINDOW_DEFAULT,
    prior_7d_avg,
    trailing_band_point,
)
from app.domains.garmin_health.contracts import (
    DailyMetric,
    DayHrv,
    HrvValue,
)
from app.domains.garmin_health.domain.daily_metrics import (
    classify_hrv_recovery,
    normalize_hrv_status,
)
from app.utils.numeric import optional_float


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


def _compute_streak(metrics: list[DailyMetric], selected_index: int) -> HrvStreak:
    """Count consecutive days ending on the selected day that share its HRV status.

    Internal input to ``low_status_streak_rule`` only — not serialized on the response.
    """
    current_status = normalize_hrv_status(metrics[selected_index].hrv.status)
    streak_days = 1
    for i in range(selected_index - 1, -1, -1):
        if normalize_hrv_status(metrics[i].hrv.status) == current_status:
            streak_days += 1
        else:
            break

    return HrvStreak(current_status=current_status, streak_days=streak_days)


def _compute_baseline(
    metrics: list[DailyMetric],
    selected_index: int,
    baseline_7d: float | None,
    window: int,
) -> HrvBaseline | None:
    """Selected-day comparison against its trailing robust baseline."""
    nightly = [m.hrv.nightly_avg for m in metrics]
    # Only the selected index is needed — compute that single point instead of the band
    # for the whole series (the /insights endpoint is not cached).
    point = trailing_band_point(
        nightly, selected_index, window=window, min_days=BASELINE_MIN_DAYS
    )
    if point.median is None:
        return None
    delta = (
        round(baseline_7d - point.median, 1) if baseline_7d is not None else None
    )
    return HrvBaseline(
        baseline=point.median,
        delta_7d_vs_baseline=delta,
        window_days=window,
        selected_z=point.z,
        selected_is_extreme=point.is_extreme,
    )


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
    window: int = BASELINE_WINDOW_DEFAULT,
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
    streak = _compute_streak(metrics, selected_index)
    baseline = _compute_baseline(
        metrics, selected_index, recovery.baseline_nightly_7d, window,
    )
    resting_delta = _resting_delta_vs_recent(metrics, selected_index)
    insights = build_hrv_insights(InsightContext(
        selected=selected_metric,
        recovery=recovery,
        quality=quality,
        resting_delta=resting_delta,
        streak=streak,
        baseline=baseline,
    ))

    return HrvInsightsResponse(
        date=selected_date,
        day_stats=selected_metric.hrv,
        recovery=recovery,
        quality=quality,
        baseline=baseline,
        insights=insights,
    )
