"""Dashboard overview assembly for Garmin analytics.

Maps the validated `recovery_score` domain computation onto the API contract: the
recovery trajectory, the state (band x trend), the meaningful-change badge, the
per-input evidence rows, and the two health flags. All statistics live in
`recovery_score`; this module only shapes the response and derives the two flags +
their recency from the loaded metrics. The per-metric detail endpoints are untouched —
the evidence rows and flags link out to those existing tabs.
"""

from collections.abc import Callable
from typing import Literal, cast

import numpy as np

from app.domains.garmin_analytics.contracts import (
    CorrelationPoint,
    DashboardOverviewResponse,
    DriverSeries,
    EvidenceRow,
    HealthFlag,
    MeaningfulChange,
    MetricCorrelation,
    RecoveryScorePoint,
    RecoveryState,
    SparkPoint,
    StructuralGap,
    TrajectoryEvent,
)
from app.domains.garmin_analytics.contracts.dashboard import (
    Band,
    FlagState,
    SourceType,
    Trend,
)
from app.domains.garmin_analytics.domain.recovery_score import flags as flag_rules
from app.domains.garmin_analytics.domain.recovery_score import regimes as regime_rules
from app.domains.garmin_analytics.domain.recovery_score import thresholds
from app.domains.garmin_analytics.domain.recovery_score.evidence import (
    RecoveryComputation,
    compute_recovery,
)
from app.domains.garmin_health.contracts import DailyMetric

_OXYGEN_TAB = "/pulse-ox"
_THERMO_TAB = "/skin-temp"
_RECENT_WINDOW = 7


def _round_opt(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _state(score_z: float | None, delta7_z: float | None) -> RecoveryState:
    if score_z is None:
        return RecoveryState()
    band = cast(Band, thresholds.score_band(score_z))
    trend = (
        cast(Trend, thresholds.trend_direction(delta7_z))
        if delta7_z is not None
        else None
    )
    return RecoveryState(band=band, trend=trend, score_z=_round_opt(score_z, 2))


def _change(delta7_z: float | None, delta1_z: float | None) -> MeaningfulChange:
    return MeaningfulChange(
        delta7_z=_round_opt(delta7_z, 2),
        is_meaningful=delta7_z is not None and thresholds.is_meaningful_delta7(delta7_z),
        direction=(
            None
            if delta7_z is None
            else cast(Trend, thresholds.trend_direction(delta7_z))
        ),
        delta1_z=_round_opt(delta1_z, 2),
        is_acute=delta1_z is not None and thresholds.is_acute_delta1(delta1_z),
    )


def _score_series(computation: RecoveryComputation) -> list[RecoveryScorePoint]:
    return [
        RecoveryScorePoint(
            date=point.date,
            raw=_round_opt(point.raw, 3),
            ma7=_round_opt(point.ma7, 3),
            baseline_lo=point.baseline_lo,
            baseline_hi=point.baseline_hi,
        )
        for point in computation.score_series
    ]


def _driver_series(computation: RecoveryComputation) -> list[DriverSeries]:
    return [
        DriverSeries(
            metric=series.metric,
            values=[_round_opt(v, 1) for v in series.values],
            baselines=[_round_opt(b, 1) for b in series.baselines],
            deltas_z=[_round_opt(z, 2) for z in series.deltas_z],
            recovery_good=series.recovery_good,
        )
        for series in computation.driver_series
    ]


def _events(computation: RecoveryComputation) -> list[TrajectoryEvent]:
    """Sustained low/elevated regimes detected from the displayed MA7 score."""
    dates = [point.date for point in computation.score_series]
    ma7 = [point.ma7 for point in computation.score_series]
    return [
        TrajectoryEvent(
            start=regime.start,
            end=regime.end,
            kind=cast(Literal["low", "elevated"], regime.kind),
            label=regime.label,
        )
        for regime in regime_rules.detect_regimes(dates, ma7)
    ]


def _evidence(computation: RecoveryComputation) -> list[EvidenceRow]:
    rows = [
        EvidenceRow(
            metric=row.metric,
            label=row.label,
            tab_href=row.tab_href,
            source_type=cast(SourceType, row.source_type),
            latest_value=row.latest_value,
            unit=row.unit,
            baseline=None if row.baseline is None else round(row.baseline, 1),
            delta_z=None if row.delta_z is None else round(row.delta_z, 2),
            delta_raw=None if row.delta_raw is None else round(row.delta_raw, 1),
            recovery_good=row.recovery_good,
            coverage_ok=row.coverage_ok,
            degraded=row.degraded,
            sparkline=[SparkPoint(date=p.date, value=p.value) for p in row.sparkline],
        )
        for row in computation.evidence
    ]
    # Largest mover first — preattentive emphasis on what drove the score (R8).
    rows.sort(key=lambda r: abs(r.delta_z) if r.delta_z is not None else -1.0, reverse=True)
    return rows


def _recent_flag(
    series: list[float | None],
    flag_fn: Callable[..., tuple[str, object]],
) -> bool:
    """Whether `flag_fn` reports 'flag' on any of the trailing _RECENT_WINDOW days.

    Each day is evaluated against its own prior history, mirroring how the latest-day
    flag is computed.
    """
    return any(
        flag_fn(series[i], history=series[:i])[0] == "flag"
        for i in range(max(0, len(series) - _RECENT_WINDOW), len(series))
    )


def _oxygen_flag(metrics: list[DailyMetric]) -> HealthFlag:
    series = [m.spo2.avg for m in metrics]
    state, threshold = flag_rules.oxygen_flag_state(series[-1], history=series[:-1])
    return HealthFlag(
        kind="oxygen",
        state=cast(FlagState, state),
        label="Oxygen",
        value=series[-1],
        threshold_low=_round_opt(threshold, 1),
        direction="low" if state == "flag" else None,
        recent=_recent_flag(series, flag_rules.oxygen_flag_state),
        tab_href=_OXYGEN_TAB,
    )


def _thermo_flag(metrics: list[DailyMetric]) -> HealthFlag:
    series = [m.skin_temp.deviation for m in metrics]
    latest = series[-1]
    state, band = flag_rules.thermo_flag_state(latest, history=series[:-1])
    direction: str | None = None
    if state == "flag" and band is not None and latest is not None:
        direction = "below" if latest < band[0] else "above"
    return HealthFlag(
        kind="thermoregulation",
        state=cast(FlagState, state),
        label="Thermoregulation",
        value=latest,
        threshold_low=_round_opt(band[0], 2) if band is not None else None,
        threshold_high=_round_opt(band[1], 2) if band is not None else None,
        direction=direction,
        recent=_recent_flag(series, flag_rules.thermo_flag_state),
        tab_href=_THERMO_TAB,
    )


def _spo2_gaps(metrics: list[DailyMetric]) -> list[StructuralGap]:
    dates = [m.date for m in metrics]
    present = [m.spo2.avg is not None for m in metrics]
    return [
        StructuralGap(start=start, end=end)
        for start, end in flag_rules.structural_gaps(dates, present)
    ]


_MIN_CORRELATION_POINTS = 7


def _correlations(metrics: list[DailyMetric]) -> list[MetricCorrelation]:
    """Nightly-HRV-vs-sleep/resting-HR scatters for the HRV detail tab (not the overview)."""
    pairings: list[tuple[str, str]] = [
        ("sleep_score", "Sleep Score"),
        ("resting_hr", "Resting HR"),
    ]
    results: list[MetricCorrelation] = []
    for metric_key, label in pairings:
        points: list[CorrelationPoint] = []
        for metric in metrics:
            nightly = metric.hrv.nightly_avg
            other = (
                metric.sleep.score
                if metric_key == "sleep_score"
                else metric.heart_rate.resting
            )
            if nightly is None or other is None:
                continue
            points.append(
                CorrelationPoint(
                    date=metric.date, hrv_nightly=nightly, other_value=float(other)
                )
            )
        if len(points) < _MIN_CORRELATION_POINTS:
            continue
        x = [point.hrv_nightly for point in points]
        y = [point.other_value for point in points]
        r_value: float | None = None
        if min(x) != max(x) and min(y) != max(y):
            r_raw = float(np.corrcoef(x, y)[0, 1])
            r_value = None if np.isnan(r_raw) else round(r_raw, 2)
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
    """Compute the latest recovery dashboard overview from ordered daily metrics."""
    computation = compute_recovery(metrics)
    if computation is None:
        return DashboardOverviewResponse(date=metrics[-1].date if metrics else "")

    return DashboardOverviewResponse(
        date=computation.date,
        state=_state(computation.score_z, computation.delta7_z),
        score=_score_series(computation),
        change=_change(computation.delta7_z, computation.delta1_z),
        evidence=_evidence(computation),
        driver_series=_driver_series(computation),
        flags=[_oxygen_flag(metrics), _thermo_flag(metrics)],
        spo2_gaps=_spo2_gaps(metrics),
        events=_events(computation),
        correlations=_correlations(metrics),
    )
