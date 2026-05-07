"""Heart-rate insight calculations for Garmin analytics."""

from datetime import datetime
from statistics import median

from app.domains.garmin_analytics.contracts import (
    DailyMetric,
    DayWellness,
    HeartRateDataQuality,
    HeartRateInsight,
    HeartRateInsightsResponse,
    HeartRateReading,
    HeartRateRecovery,
    HRZoneDuration,
)
from app.domains.garmin_analytics.domain.aggregates.daily import (
    HR_ZONE_THRESHOLDS,
    is_balanced_hrv_status,
    is_unfavorable_hrv_status,
)
from app.domains.garmin_analytics.domain.primitives.timestamps import (
    summarize_timestamp_coverage,
)
from app.domains.garmin_analytics.domain.primitives.trends import prior_7d_avg
from app.utils.timeutil import parse_iso as _parse_iso


def zone_for_value(value: int) -> tuple[str, int, int | None] | None:
    for label, lower, upper in HR_ZONE_THRESHOLDS:
        if value >= lower and (upper is None or value < upper):
            return (label, lower, upper)
    return None


def estimate_default_interval_minutes(readings: list[tuple[datetime, int]]) -> float:
    if len(readings) < 2:
        return 1.0
    deltas = []
    for i in range(len(readings) - 1):
        delta = (readings[i + 1][0] - readings[i][0]).total_seconds() / 60.0
        if delta > 0:
            deltas.append(delta)
    if not deltas:
        return 1.0
    return max(0.25, min(float(median(deltas)), 5.0))


def compute_zone_minutes(hr_readings: list[HeartRateReading]) -> list[HRZoneDuration]:
    resolved: list[tuple[datetime, int]] = []
    for reading in hr_readings:
        if reading.value == 0:
            continue
        dt = _parse_iso(reading.timestamp)
        if dt is None:
            continue
        resolved.append((dt, reading.value))

    if not resolved:
        return []

    resolved.sort(key=lambda item: item[0])
    default_interval = estimate_default_interval_minutes(resolved)
    max_interval = max(default_interval * 3, 1.0)

    buckets: dict[tuple[str, int, int | None], float] = {}
    for i, (dt, value) in enumerate(resolved):
        zone = zone_for_value(value)
        if zone is None:
            continue

        if i == len(resolved) - 1:
            interval = default_interval
        else:
            interval = (resolved[i + 1][0] - dt).total_seconds() / 60.0
            interval = min(interval, max_interval)

        if interval <= 0:
            continue
        buckets[zone] = buckets.get(zone, 0.0) + interval

    total_minutes = sum(buckets.values())
    if total_minutes <= 0:
        return []

    result: list[HRZoneDuration] = []
    for label, lower, upper in HR_ZONE_THRESHOLDS:
        minutes = buckets.get((label, lower, upper), 0.0)
        if minutes <= 0:
            continue
        result.append(HRZoneDuration(
            label=label,
            min_bpm=lower,
            max_bpm=upper,
            minutes=round(minutes, 1),
            pct=round(minutes / total_minutes * 100, 1),
        ))
    return result


def compute_recovery(metrics: list[DailyMetric], selected_index: int) -> HeartRateRecovery:
    selected_resting = metrics[selected_index].heart_rate.resting
    baseline = prior_7d_avg(
        metrics,
        selected_index,
        lambda m: float(m.heart_rate.resting) if m.heart_rate.resting is not None else None,
    )
    delta = (
        round(selected_resting - baseline, 1)
        if selected_resting is not None and baseline is not None else None
    )
    status: str | None
    if delta is None:
        status = None
    elif delta >= 6:
        status = "high"
    elif delta >= 3:
        status = "elevated"
    elif delta <= -3:
        status = "low"
    else:
        status = "normal"

    return HeartRateRecovery(
        baseline_resting_7d=baseline,
        delta_from_baseline=delta,
        status=status,
    )


def build_insights(
    selected: DailyMetric,
    recovery: HeartRateRecovery,
    quality: HeartRateDataQuality,
) -> list[HeartRateInsight]:
    insights: list[HeartRateInsight] = []

    delta = recovery.delta_from_baseline
    status = recovery.status
    sleep_score = selected.sleep.score

    if status == "high":
        insights.append(HeartRateInsight(
            level="warning",
            title="Resting HR is materially elevated",
            detail=f"Resting HR is {delta:+.1f} bpm versus the prior 7-day baseline.",
        ))
    elif status == "elevated":
        insights.append(HeartRateInsight(
            level="caution",
            title="Resting HR is mildly elevated",
            detail=f"Resting HR is {delta:+.1f} bpm versus the prior 7-day baseline.",
        ))
    elif status == "low":
        insights.append(HeartRateInsight(
            level="good",
            title="Resting HR is below baseline",
            detail=f"Resting HR is {delta:+.1f} bpm versus the prior 7-day baseline.",
        ))

    if sleep_score is not None and sleep_score < 70 and status in {"high", "elevated"}:
        insights.append(HeartRateInsight(
            level="warning",
            title="Sleep may be impacting recovery",
            detail=f"Sleep score is {sleep_score}, which often coincides with elevated resting HR.",
        ))

    hrv_unfavorable = is_unfavorable_hrv_status(selected.hrv.status)
    if hrv_unfavorable and status in {"high", "elevated"}:
        insights.append(HeartRateInsight(
            level="warning",
            title="HRV and resting HR are both unfavorable",
            detail=f"HRV status is '{selected.hrv.status}', while resting HR is above baseline.",
        ))

    if (
        not insights
        and sleep_score is not None
        and sleep_score >= 80
        and is_balanced_hrv_status(selected.hrv.status)
    ):
        insights.append(HeartRateInsight(
            level="good",
            title="Recovery signals look stable",
            detail="Sleep score and HRV status are supportive, with no elevated resting-HR signal.",
        ))

    if quality.sample_count < 30:
        insights.append(HeartRateInsight(
            level="info",
            title="Low sample coverage",
            detail=f"Only {quality.sample_count} heart-rate samples were available for this day.",
        ))

    return insights


def compute_heart_rate_insights(
    metrics: list[DailyMetric],
    selected_date: str,
    wellness_days: list[DayWellness],
) -> HeartRateInsightsResponse:
    selected_index = next(
        (i for i, metric in enumerate(metrics) if metric.date == selected_date),
        None,
    )
    if selected_index is None:
        raise LookupError(f"Day {selected_date} not found")

    heart_rate_readings = wellness_days[0].heart_rate if wellness_days else []
    coverage = summarize_timestamp_coverage(
        [reading.timestamp for reading in heart_rate_readings]
    )

    quality = HeartRateDataQuality(
        sample_count=coverage.sample_count,
        coverage_start=coverage.coverage_start,
        coverage_end=coverage.coverage_end,
        coverage_hours=coverage.coverage_hours,
    )
    recovery = compute_recovery(metrics, selected_index)
    selected_metric = metrics[selected_index]

    return HeartRateInsightsResponse(
        date=selected_date,
        day_stats=selected_metric.heart_rate,
        recovery=recovery,
        zones=compute_zone_minutes(heart_rate_readings),
        quality=quality,
        insights=build_insights(selected_metric, recovery, quality),
    )
