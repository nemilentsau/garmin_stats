"""HRV domain service: backend source of truth for derived HRV insights."""

from collections import Counter
from datetime import datetime

import numpy as np

from ..database import load_daily_metrics, load_hrv
from ..models import (
    DailyMetric,
    HrvDataQuality,
    HrvInsight,
    HrvInsightsResponse,
    HrvRecovery,
    HrvStatusBucket,
    HrvTrendBand,
)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    normalized = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_hrv_status(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    value = raw.lower()
    if "balanced" in value:
        return "Balanced"
    if "low" in value:
        return "Low"
    if "unbalanced" in value:
        return "Unbalanced"
    if "high" in value:
        return "High"
    return raw.title()


def _compute_recovery(metrics: list[DailyMetric], selected_index: int) -> HrvRecovery:
    selected = metrics[selected_index].hrv
    previous_nightly = [
        metric.hrv.nightly_avg
        for metric in metrics[max(0, selected_index - 7):selected_index]
        if metric.hrv.nightly_avg is not None
    ]
    baseline = (
        round(sum(previous_nightly) / len(previous_nightly), 1)
        if previous_nightly else None
    )
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


def _compute_quality(date: str) -> HrvDataQuality:
    day_rows = load_hrv(date)
    hrv_values = day_rows[0].hrv_values if day_rows else []
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


def _compute_trend_band(metrics: list[DailyMetric]) -> HrvTrendBand:
    nightly_vals = [
        metric.hrv.nightly_avg
        for metric in metrics
        if metric.hrv.nightly_avg is not None
    ]
    if len(nightly_vals) < 2:
        return HrvTrendBand()
    low = round(float(np.percentile(nightly_vals, 25)), 1)
    high = round(float(np.percentile(nightly_vals, 75)), 1)
    return HrvTrendBand(nightly_typical_low=low, nightly_typical_high=high)


def _compute_status_mix(metrics: list[DailyMetric], selected_index: int) -> list[HrvStatusBucket]:
    window = metrics[max(0, selected_index - 13):selected_index + 1]
    labels = [
        _normalize_hrv_status(metric.hrv.status)
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


def _resting_delta_vs_recent(metrics: list[DailyMetric], selected_index: int) -> float | None:
    selected_resting = metrics[selected_index].heart_rate.resting
    previous_resting = [
        metric.heart_rate.resting
        for metric in metrics[max(0, selected_index - 7):selected_index]
        if metric.heart_rate.resting is not None
    ]
    if selected_resting is None or not previous_resting:
        return None
    baseline = sum(previous_resting) / len(previous_resting)
    return round(selected_resting - baseline, 1)


def _build_insights(
    selected: DailyMetric,
    recovery: HrvRecovery,
    quality: HrvDataQuality,
    resting_delta: float | None,
) -> list[HrvInsight]:
    insights: list[HrvInsight] = []
    status = recovery.status

    if status == "suppressed":
        insights.append(HrvInsight(
            level="warning",
            title="HRV appears suppressed",
            detail=(
                f"Nightly HRV is {recovery.delta_nightly_from_baseline:+.1f} ms versus the "
                "prior 7-day baseline."
            )
            if recovery.delta_nightly_from_baseline is not None
            else "Nightly HRV is below expected levels.",
        ))
    elif status == "below_baseline":
        insights.append(HrvInsight(
            level="caution",
            title="HRV is below baseline",
            detail=(
                f"Nightly HRV is {recovery.delta_nightly_from_baseline:+.1f} ms versus the "
                "prior 7-day baseline."
            )
            if recovery.delta_nightly_from_baseline is not None
            else "Nightly HRV is mildly below baseline.",
        ))
    elif status == "elevated":
        insights.append(HrvInsight(
            level="good",
            title="HRV is above baseline",
            detail=(
                f"Nightly HRV is {recovery.delta_nightly_from_baseline:+.1f} ms versus the "
                "prior 7-day baseline."
            )
            if recovery.delta_nightly_from_baseline is not None
            else "Nightly HRV is above baseline.",
        ))

    if recovery.acute_gap_vs_weekly is not None and recovery.acute_gap_vs_weekly <= -8:
        insights.append(HrvInsight(
            level="caution",
            title="Acute recovery is below weekly trend",
            detail=(
                f"Nightly HRV is {recovery.acute_gap_vs_weekly:+.1f} ms versus weekly average, "
                "which can indicate short-term strain."
            ),
        ))

    sleep_score = selected.sleep.score
    if sleep_score is not None and sleep_score < 70 and status in {"suppressed", "below_baseline"}:
        insights.append(HrvInsight(
            level="warning",
            title="Sleep and HRV both indicate reduced recovery",
            detail=f"Sleep score is {sleep_score}, aligning with lower-than-baseline HRV.",
        ))

    if (
        resting_delta is not None
        and resting_delta >= 4
        and status in {"suppressed", "below_baseline"}
    ):
        insights.append(HrvInsight(
            level="warning",
            title="Resting HR and HRV are diverging unfavorably",
            detail=(
                f"Resting HR is +{resting_delta:.1f} bpm versus recent baseline "
                "while HRV is below baseline."
            ),
        ))

    if (
        not insights
        and sleep_score is not None
        and sleep_score >= 80
        and selected.hrv.status
        and "balanced" in selected.hrv.status.lower()
    ):
        insights.append(HrvInsight(
            level="good",
            title="HRV recovery signals look stable",
            detail="Balanced HRV status and strong sleep score suggest good recovery.",
        ))

    if quality.sample_count < 20:
        insights.append(HrvInsight(
            level="info",
            title="Low HRV sample coverage",
            detail=f"Only {quality.sample_count} intraday HRV values were available for this day.",
        ))

    return insights


def load_hrv_insights(date: str | None = None) -> HrvInsightsResponse:
    """Load backend-derived HRV insights for a day (or latest if omitted)."""
    metrics = load_daily_metrics()
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
    recovery = _compute_recovery(metrics, selected_index)
    quality = _compute_quality(selected_date)
    trend_band = _compute_trend_band(metrics)
    status_mix = _compute_status_mix(metrics, selected_index)
    resting_delta = _resting_delta_vs_recent(metrics, selected_index)
    insights = _build_insights(selected_metric, recovery, quality, resting_delta)

    return HrvInsightsResponse(
        date=selected_date,
        day_stats=selected_metric.hrv,
        recovery=recovery,
        quality=quality,
        trend_band=trend_band,
        status_mix=status_mix,
        insights=insights,
    )
