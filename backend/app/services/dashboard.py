"""Dashboard overview service: readiness score and cross-domain correlations."""

import numpy as np

from ..infra.database import load_daily_metrics
from ..models import (
    CorrelationPoint,
    DailyMetric,
    DashboardOverviewResponse,
    DashboardSparklines,
    MetricCorrelation,
    ReadinessScore,
    SparklinePoint,
    SparklineSeries,
    SparklineSummary,
    TodayVitals,
)
from ..stats import trailing_ma7


def _normalize_hrv_status(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    value = raw.lower()
    if value == "none":
        return "Unknown"
    if "unbalanced" in value:  # must precede "balanced" (substring match)
        return "Unbalanced"
    if "balanced" in value:
        return "Balanced"
    if "low" in value:
        return "Low"
    if "high" in value:
        return "High"
    return raw.title()


def _recovery_status(
    metrics: list[DailyMetric], selected_index: int,
) -> str | None:
    """Classify HRV recovery status for the selected day."""
    selected = metrics[selected_index].hrv
    nightly = selected.nightly_avg
    previous_nightly = [
        m.hrv.nightly_avg
        for m in metrics[max(0, selected_index - 7):selected_index]
        if m.hrv.nightly_avg is not None
    ]
    if nightly is None or not previous_nightly:
        return None
    baseline = sum(previous_nightly) / len(previous_nightly)
    delta = nightly - baseline
    status_text = selected.status.lower() if selected.status else ""
    if delta <= -10 or "low" in status_text or "unbalanced" in status_text:
        return "suppressed"
    if delta <= -5:
        return "below_baseline"
    if delta >= 8:
        return "elevated"
    return "stable"


def _resting_delta(
    metrics: list[DailyMetric], selected_index: int,
) -> float | None:
    """Compute resting HR delta vs prior 7-day average."""
    selected_resting = metrics[selected_index].heart_rate.resting
    previous = [
        m.heart_rate.resting
        for m in metrics[max(0, selected_index - 7):selected_index]
        if m.heart_rate.resting is not None
    ]
    if selected_resting is None or not previous:
        return None
    return round(selected_resting - sum(previous) / len(previous), 1)


def _compute_readiness(
    selected: DailyMetric,
    recovery_status: str | None,
    resting_delta: float | None,
) -> ReadinessScore | None:
    """Composite 0-100 readiness score from four recovery components."""
    if selected.sleep.score is None and selected.hrv.status is None:
        return None

    # HRV recovery (0-25)
    recovery_map = {
        "elevated": 25.0,
        "stable": 20.0,
        "below_baseline": 10.0,
        "suppressed": 0.0,
    }
    hrv_recovery = recovery_map.get(recovery_status or "", 12.0)

    # Sleep (0-25), linear from score 40→0 to 90→25
    if selected.sleep.score is not None:
        clamped = max(40, min(90, selected.sleep.score))
        sleep = round((clamped - 40) / 50 * 25, 1)
    else:
        sleep = 12.0

    # Resting HR delta (0-25): ≤-3→25, 0→20, ≥6→5, linear between
    if resting_delta is not None:
        if resting_delta <= -3:
            rhr = 25.0
        elif resting_delta <= 0:
            rhr = round(25 - (resting_delta + 3) / 3 * 5, 1)
        elif resting_delta <= 6:
            rhr = round(20 - resting_delta / 6 * 15, 1)
        else:
            rhr = 5.0
    else:
        rhr = 12.0

    # HRV status (0-25)
    status_map = {
        "Balanced": 25.0,
        "High": 20.0,
        "Low": 5.0,
        "Unbalanced": 0.0,
    }
    normalized = _normalize_hrv_status(selected.hrv.status)
    hrv_status = status_map.get(normalized, 12.0)

    total = round(hrv_recovery + sleep + rhr + hrv_status)
    if total >= 75:
        label = "Ready"
    elif total >= 50:
        label = "Moderate"
    else:
        label = "Rest"

    return ReadinessScore(
        score=total,
        components={
            "hrv_recovery": hrv_recovery,
            "sleep": sleep,
            "resting_hr": rhr,
            "hrv_status": hrv_status,
        },
        label=label,
    )


def _compute_vitals(
    metrics: list[DailyMetric], selected_index: int,
) -> TodayVitals:
    """Extract today's key vitals with 7-day deltas."""
    selected = metrics[selected_index]

    # Resting HR delta (reuse existing pattern)
    resting_delta = _resting_delta(metrics, selected_index)

    # Nightly HRV delta vs 7-day average
    nightly = selected.hrv.nightly_avg
    previous_nightly = [
        m.hrv.nightly_avg
        for m in metrics[max(0, selected_index - 7):selected_index]
        if m.hrv.nightly_avg is not None
    ]
    hrv_delta: float | None = None
    if nightly is not None and previous_nightly:
        hrv_delta = round(nightly - sum(previous_nightly) / len(previous_nightly), 1)

    return TodayVitals(
        resting_hr=selected.heart_rate.resting,
        resting_hr_delta_7d=resting_delta,
        nightly_hrv=nightly,
        nightly_hrv_delta_7d=hrv_delta,
        hrv_status=_normalize_hrv_status(selected.hrv.status),
        sleep_score=selected.sleep.score,
        stress_avg=selected.stress.avg,
    )


_SPARKLINE_DAYS = 91  # ~3 months


def _build_series(
    window: list[DailyMetric],
    raw_vals: list[float | None],
) -> SparklineSeries:
    """Build a SparklineSeries with points, MA, and summary stats."""
    ma_vals = trailing_ma7(raw_vals)
    non_null = [v for v in raw_vals if v is not None]
    summary = SparklineSummary(
        avg=round(sum(non_null) / len(non_null), 1) if non_null else None,
        min=round(min(non_null), 1) if non_null else None,
        max=round(max(non_null), 1) if non_null else None,
    )
    points = [
        SparklinePoint(date=m.date, value=raw_vals[i], ma7=ma_vals[i])
        for i, m in enumerate(window)
    ]
    return SparklineSeries(points=points, summary=summary)


def _compute_sparklines(metrics: list[DailyMetric]) -> DashboardSparklines:
    """Build 3-month sparkline data for 4 key metrics with 7-day MA."""
    window = metrics[-_SPARKLINE_DAYS:]

    return DashboardSparklines(
        resting_hr=_build_series(window, [
            float(m.heart_rate.resting) if m.heart_rate.resting is not None else None
            for m in window
        ]),
        nightly_hrv=_build_series(window, [
            m.hrv.nightly_avg for m in window
        ]),
        sleep_score=_build_series(window, [
            float(m.sleep.score) if m.sleep.score is not None else None
            for m in window
        ]),
        stress_avg=_build_series(window, [
            m.stress.avg for m in window
        ]),
    )


_MIN_CORRELATION_POINTS = 7


def _has_variation(values: list[float]) -> bool:
    return min(values) != max(values)


def _compute_correlations(
    metrics: list[DailyMetric],
) -> list[MetricCorrelation]:
    """Pearson correlation of nightly HRV vs sleep score and resting HR."""
    pairings: list[tuple[str, str, type]] = [
        ("sleep_score", "Sleep Score", int),
        ("resting_hr", "Resting HR", int),
    ]
    results: list[MetricCorrelation] = []

    for metric_key, label, _ in pairings:
        points: list[CorrelationPoint] = []
        for m in metrics:
            nightly = m.hrv.nightly_avg
            if nightly is None:
                continue
            other = m.sleep.score if metric_key == "sleep_score" else m.heart_rate.resting
            if other is None:
                continue
            points.append(CorrelationPoint(
                date=m.date,
                hrv_nightly=nightly,
                other_value=float(other),
            ))

        if len(points) < _MIN_CORRELATION_POINTS:
            continue

        x = [p.hrv_nightly for p in points]
        y = [p.other_value for p in points]
        if _has_variation(x) and _has_variation(y):
            r_raw = float(np.corrcoef(x, y)[0, 1])
            r_value = None if np.isnan(r_raw) else round(r_raw, 2)
        else:
            r_value = None

        results.append(MetricCorrelation(
            metric=metric_key,
            label=label,
            points=points,
            r_value=r_value,
            sample_count=len(points),
        ))

    return results


def load_dashboard_overview() -> DashboardOverviewResponse:
    """Load readiness score and cross-domain correlations."""
    metrics = load_daily_metrics()
    if not metrics:
        raise LookupError("No data available")

    selected_index = len(metrics) - 1
    selected = metrics[selected_index]

    rec_status = _recovery_status(metrics, selected_index)
    rest_delta = _resting_delta(metrics, selected_index)
    readiness = _compute_readiness(selected, rec_status, rest_delta)
    vitals = _compute_vitals(metrics, selected_index)
    sparklines = _compute_sparklines(metrics)
    correlations = _compute_correlations(metrics)

    return DashboardOverviewResponse(
        date=selected.date,
        readiness=readiness,
        vitals=vitals,
        sparklines=sparklines,
        correlations=correlations,
    )
