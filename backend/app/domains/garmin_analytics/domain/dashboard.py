"""Dashboard overview calculations for Garmin analytics."""

import numpy as np

from app.domains.garmin_analytics.contracts import (
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
from app.domains.garmin_analytics.domain.aggregates.daily import normalize_hrv_status
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_max,
    safe_min,
)
from app.domains.garmin_analytics.domain.primitives.trends import (
    prior_7d_avg,
    trailing_ma7,
)


def _recovery_status(
    selected: DailyMetric,
    hrv_baseline_7d: float | None,
) -> str | None:
    nightly = selected.hrv.nightly_avg
    if nightly is None or hrv_baseline_7d is None:
        return None
    delta = nightly - hrv_baseline_7d
    status_text = selected.hrv.status.lower() if selected.hrv.status else ""
    if delta <= -10:
        return "suppressed_delta"
    if "low" in status_text or "unbalanced" in status_text:
        return "suppressed_status"
    if delta <= -5:
        return "below_baseline"
    if delta >= 8:
        return "elevated"
    return "stable"


def _format_delta_magnitude(value: float) -> str:
    rounded = round(abs(value), 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def _compute_readiness(
    selected: DailyMetric,
    recovery_status: str | None,
    resting_delta: float | None,
) -> ReadinessScore | None:
    if selected.sleep.score is None and selected.hrv.status is None:
        return None

    recovery_info: dict[str, tuple[float, str]] = {
        "elevated": (25.0, "HRV rose 8+ ms above your 7-day average — strong recovery"),
        "stable": (20.0, "HRV is within normal range of your 7-day average"),
        "below_baseline": (10.0, "HRV dropped 5—10 ms below your 7-day average"),
        "suppressed_delta": (
            0.0,
            "HRV dropped 10+ ms below your 7-day average — suppressed",
        ),
    }
    if recovery_status == "suppressed_status":
        normalized_status = normalize_hrv_status(selected.hrv.status).lower()
        hrv_recovery = 0.0
        hrv_recovery_hint = (
            f"Garmin HRV status is {normalized_status}, which suppresses recovery "
            "without a 10+ ms drop vs your 7-day average"
        )
    else:
        hrv_recovery, hrv_recovery_hint = recovery_info.get(
            recovery_status or "",
            (12.0, "Insufficient data for recovery assessment"),
        )

    if selected.sleep.score is not None:
        clamped = max(40, min(90, selected.sleep.score))
        sleep = round((clamped - 40) / 50 * 25, 1)
        sleep_score = selected.sleep.score
        if sleep_score >= 80:
            sleep_hint = f"Sleep score {sleep_score} — excellent quality"
        elif sleep_score >= 60:
            sleep_hint = f"Sleep score {sleep_score} — moderate quality"
        else:
            sleep_hint = f"Sleep score {sleep_score} — poor quality"
    else:
        sleep = 12.0
        sleep_hint = "No sleep data available"

    if resting_delta is not None:
        abs_delta_text = _format_delta_magnitude(resting_delta)
        if resting_delta <= -3:
            rhr = 25.0
            rhr_hint = (
                f"Resting HR is {abs_delta_text} bpm below "
                "7-day average — great recovery"
            )
        elif resting_delta <= 0:
            rhr = round(25 - (resting_delta + 3) / 3 * 5, 1)
            rhr_hint = "Resting HR is near your 7-day average"
        elif resting_delta <= 6:
            rhr = round(20 - resting_delta / 6 * 15, 1)
            rhr_hint = (
                f"Resting HR is {abs_delta_text} bpm above "
                "7-day average — possible stress"
            )
        else:
            rhr = 5.0
            rhr_hint = (
                f"Resting HR is {abs_delta_text} bpm above "
                "7-day average — significant elevation"
            )
    else:
        rhr = 12.0
        rhr_hint = "No resting HR baseline available"

    status_info: dict[str, tuple[float, str]] = {
        "Balanced": (25.0, "Autonomic nervous system is well-balanced"),
        "High": (20.0, "HRV is elevated — good recovery or detraining"),
        "Low": (5.0, "HRV is persistently low — may indicate fatigue"),
        "Unbalanced": (0.0, "Autonomic nervous system shows imbalance"),
    }
    normalized = normalize_hrv_status(selected.hrv.status)
    hrv_status, hrv_status_hint = status_info.get(
        normalized,
        (12.0, "HRV status unavailable"),
    )

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
        component_hints={
            "hrv_recovery": hrv_recovery_hint,
            "sleep": sleep_hint,
            "resting_hr": rhr_hint,
            "hrv_status": hrv_status_hint,
        },
        label=label,
    )


def _compute_vitals(
    selected: DailyMetric,
    resting_delta: float | None,
    hrv_baseline_7d: float | None,
) -> TodayVitals:
    nightly = selected.hrv.nightly_avg
    hrv_delta: float | None = None
    if nightly is not None and hrv_baseline_7d is not None:
        hrv_delta = round(nightly - hrv_baseline_7d, 1)

    return TodayVitals(
        resting_hr=selected.heart_rate.resting,
        resting_hr_delta_7d=resting_delta,
        nightly_hrv=nightly,
        nightly_hrv_delta_7d=hrv_delta,
        hrv_status=normalize_hrv_status(selected.hrv.status),
        sleep_score=selected.sleep.score,
        stress_avg=selected.stress.avg,
    )


_SPARKLINE_DAYS = 91


def _build_series(
    window: list[DailyMetric],
    raw_vals: list[float | None],
) -> SparklineSeries:
    ma_vals = trailing_ma7(raw_vals)
    non_null = [value for value in raw_vals if value is not None]
    summary = SparklineSummary(
        avg=safe_avg(non_null),
        min=safe_min(non_null),
        max=safe_max(non_null),
    )
    points = [
        SparklinePoint(date=metric.date, value=raw_vals[index], ma7=ma_vals[index])
        for index, metric in enumerate(window)
    ]
    return SparklineSeries(points=points, summary=summary)


def _compute_sparklines(metrics: list[DailyMetric]) -> DashboardSparklines:
    window = metrics[-_SPARKLINE_DAYS:]
    return DashboardSparklines(
        resting_hr=_build_series(
            window,
            [
                float(metric.heart_rate.resting)
                if metric.heart_rate.resting is not None
                else None
                for metric in window
            ],
        ),
        nightly_hrv=_build_series(window, [metric.hrv.nightly_avg for metric in window]),
        sleep_score=_build_series(
            window,
            [
                float(metric.sleep.score) if metric.sleep.score is not None else None
                for metric in window
            ],
        ),
        stress_avg=_build_series(window, [metric.stress.avg for metric in window]),
    )


_MIN_CORRELATION_POINTS = 7


def _has_variation(values: list[float]) -> bool:
    return min(values) != max(values)


def _compute_correlations(metrics: list[DailyMetric]) -> list[MetricCorrelation]:
    pairings = [
        ("sleep_score", "Sleep Score"),
        ("resting_hr", "Resting HR"),
    ]
    results: list[MetricCorrelation] = []

    for metric_key, label in pairings:
        points: list[CorrelationPoint] = []
        for metric in metrics:
            nightly = metric.hrv.nightly_avg
            if nightly is None:
                continue
            other = (
                metric.sleep.score
                if metric_key == "sleep_score"
                else metric.heart_rate.resting
            )
            if other is None:
                continue
            points.append(
                CorrelationPoint(
                    date=metric.date,
                    hrv_nightly=nightly,
                    other_value=float(other),
                )
            )

        if len(points) < _MIN_CORRELATION_POINTS:
            continue

        x = [point.hrv_nightly for point in points]
        y = [point.other_value for point in points]
        if _has_variation(x) and _has_variation(y):
            r_raw = float(np.corrcoef(x, y)[0, 1])
            r_value = None if np.isnan(r_raw) else round(r_raw, 2)
        else:
            r_value = None

        results.append(
            MetricCorrelation(
                metric=metric_key,
                label=label,
                points=points,
                r_value=r_value,
                sample_count=len(points),
            )
        )

    return results


def compute_dashboard_overview(metrics: list[DailyMetric]) -> DashboardOverviewResponse:
    selected_index = len(metrics) - 1
    selected = metrics[selected_index]

    hrv_baseline_7d = prior_7d_avg(metrics, selected_index, lambda m: m.hrv.nightly_avg)
    resting_baseline_7d = prior_7d_avg(
        metrics, selected_index,
        lambda m: float(m.heart_rate.resting) if m.heart_rate.resting is not None else None,
    )
    resting_delta = (
        round(selected.heart_rate.resting - resting_baseline_7d, 1)
        if selected.heart_rate.resting is not None and resting_baseline_7d is not None
        else None
    )
    readiness = _compute_readiness(
        selected,
        _recovery_status(selected, hrv_baseline_7d),
        resting_delta,
    )

    return DashboardOverviewResponse(
        date=selected.date,
        readiness=readiness,
        vitals=_compute_vitals(selected, resting_delta, hrv_baseline_7d),
        sparklines=_compute_sparklines(metrics),
        correlations=_compute_correlations(metrics),
    )
