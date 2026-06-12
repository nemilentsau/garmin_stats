"""Dashboard overview assembly for Garmin analytics.

Maps the validated `recovery_score` domain computation onto the API contract: the
recovery trajectory, the state (band x trend), the meaningful-change badge, the
per-input evidence rows, and the two health flags. All statistics live in
`recovery_score`; this module only shapes the response and derives the two flags +
their recency from the loaded metrics. The per-metric detail endpoints are untouched —
the evidence rows and flags link out to those existing tabs.
"""

from typing import cast

from app.domains.garmin_analytics.contracts import (
    DashboardOverviewResponse,
    EvidenceRow,
    HealthFlag,
    MeaningfulChange,
    RecoveryScorePoint,
    RecoveryState,
    SparkPoint,
    StructuralGap,
)
from app.domains.garmin_analytics.contracts.dashboard import (
    Band,
    FlagState,
    SourceType,
    Trend,
)
from app.domains.garmin_analytics.domain.recovery_score import flags as flag_rules
from app.domains.garmin_analytics.domain.recovery_score import thresholds
from app.domains.garmin_analytics.domain.recovery_score.evidence import (
    RecoveryComputation,
    compute_recovery,
)
from app.domains.garmin_health.contracts import DailyMetric

_OXYGEN_TAB = "/pulse-ox"
_THERMO_TAB = "/skin-temp"
_RECENT_WINDOW = 7


def _state(score_z: float | None, delta7_z: float | None) -> RecoveryState:
    if score_z is None:
        return RecoveryState()
    band = cast(Band, thresholds.score_band(score_z))
    trend = (
        cast(Trend, thresholds.trend_direction(delta7_z))
        if delta7_z is not None
        else None
    )
    return RecoveryState(band=band, trend=trend, score_z=round(score_z, 2))


def _change(delta7_z: float | None, delta1_z: float | None) -> MeaningfulChange:
    return MeaningfulChange(
        delta7_z=None if delta7_z is None else round(delta7_z, 2),
        is_meaningful=delta7_z is not None and thresholds.is_meaningful_delta7(delta7_z),
        direction=(
            None
            if delta7_z is None
            else cast(Trend, thresholds.trend_direction(delta7_z))
        ),
        delta1_z=None if delta1_z is None else round(delta1_z, 2),
        is_acute=delta1_z is not None and thresholds.is_acute_delta1(delta1_z),
    )


def _score_series(computation: RecoveryComputation) -> list[RecoveryScorePoint]:
    return [
        RecoveryScorePoint(
            date=point.date,
            raw=None if point.raw is None else round(point.raw, 3),
            ma7=None if point.ma7 is None else round(point.ma7, 3),
            baseline_lo=point.baseline_lo,
            baseline_hi=point.baseline_hi,
        )
        for point in computation.score_series
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


def _recent_oxygen(values: list[float | None], histories: list[list[float | None]]) -> bool:
    """Whether the oxygen flag fired on any of the trailing days."""
    return any(
        flag_rules.oxygen_flag_state(value, history=history)[0] == "flag"
        for value, history in zip(values, histories, strict=True)
    )


def _recent_thermo(values: list[float | None], histories: list[list[float | None]]) -> bool:
    return any(
        flag_rules.thermo_flag_state(value, history=history)[0] == "flag"
        for value, history in zip(values, histories, strict=True)
    )


def _oxygen_flag(metrics: list[DailyMetric]) -> HealthFlag:
    series = [m.spo2.avg for m in metrics]
    latest = series[-1]
    history = series[:-1]
    state, threshold = flag_rules.oxygen_flag_state(latest, history=history)
    recent_values = series[-_RECENT_WINDOW:]
    recent_histories = [
        series[: len(series) - _RECENT_WINDOW + i] for i in range(len(recent_values))
    ]
    return HealthFlag(
        kind="oxygen",
        state=cast(FlagState, state),
        label="Oxygen",
        value=latest,
        threshold_low=None if threshold is None else round(threshold, 1),
        direction="low" if state == "flag" else None,
        recent=_recent_oxygen(recent_values, recent_histories),
        tab_href=_OXYGEN_TAB,
    )


def _thermo_flag(metrics: list[DailyMetric]) -> HealthFlag:
    series = [m.skin_temp.deviation for m in metrics]
    latest = series[-1]
    history = series[:-1]
    state, band = flag_rules.thermo_flag_state(latest, history=history)
    direction: str | None = None
    if state == "flag" and band is not None and latest is not None:
        direction = "below" if latest < band[0] else "above"
    recent_values = series[-_RECENT_WINDOW:]
    recent_histories = [
        series[: len(series) - _RECENT_WINDOW + i] for i in range(len(recent_values))
    ]
    return HealthFlag(
        kind="thermoregulation",
        state=cast(FlagState, state),
        label="Thermoregulation",
        value=latest,
        threshold_low=None if band is None else round(band[0], 2),
        threshold_high=None if band is None else round(band[1], 2),
        direction=direction,
        recent=_recent_thermo(recent_values, recent_histories),
        tab_href=_THERMO_TAB,
    )


def _spo2_gaps(metrics: list[DailyMetric]) -> list[StructuralGap]:
    dates = [m.date for m in metrics]
    present = [m.spo2.avg is not None for m in metrics]
    return [
        StructuralGap(start=start, end=end)
        for start, end in flag_rules.structural_gaps(dates, present)
    ]


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
        flags=[_oxygen_flag(metrics), _thermo_flag(metrics)],
        spo2_gaps=_spo2_gaps(metrics),
    )
