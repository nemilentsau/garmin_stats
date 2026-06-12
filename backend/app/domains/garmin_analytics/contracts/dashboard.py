"""Recovery dashboard overview response contracts.

The overview surfaces the validated single-axis recovery score (R1–R6), its
meaningful-change state (R2 + Q4.1), the per-input evidence that drove it (R8), and the
two health flags (R9). Every value is computed in the `recovery_score` domain; the
frontend is display-only. Evidence rows and flags carry a `tab_href` linking to the
existing per-metric detail tabs, which the overview complements rather than replaces.
"""

from typing import Literal

from app.contracts.base import DefaultsRequired

Band = Literal["suppressed", "typical", "strong"]
Trend = Literal["improving", "steady", "declining"]
SourceType = Literal["native", "device", "derived"]
FlagKind = Literal["oxygen", "thermoregulation"]
FlagState = Literal["clear", "flag", "unknown"]


class SparkPoint(DefaultsRequired):
    """One dated point in an inline evidence sparkline (raw metric value)."""

    date: str
    value: float | None = None


class RecoveryScorePoint(DefaultsRequired):
    """One day of the recovery trajectory: raw score, seeded MA7, and typical band."""

    date: str
    raw: float | None = None
    ma7: float | None = None
    baseline_lo: float
    baseline_hi: float


class RecoveryState(DefaultsRequired):
    """The 'state before score' label: a continuum band x trend (Q4.1), not an archetype."""

    band: Band | None = None
    trend: Trend | None = None
    score_z: float | None = None


class MeaningfulChange(DefaultsRequired):
    """Sustained (Δ7) and acute (Δ1) change of the score against the R2 thresholds."""

    delta7_z: float | None = None
    is_meaningful: bool = False
    direction: Trend | None = None
    comparison_label: str = "vs prior week"
    delta1_z: float | None = None
    is_acute: bool = False


class EvidenceRow(DefaultsRequired):
    """One recovery input's contribution to today's score, linking to its detail tab."""

    metric: str
    label: str
    tab_href: str
    source_type: SourceType
    latest_value: float | None = None
    unit: str = ""
    baseline: float | None = None
    delta_z: float | None = None       # raw z (metric vs baseline, natural direction)
    delta_raw: float | None = None     # latest_value - baseline, raw units
    recovery_good: bool | None = None  # whether this move helps recovery
    coverage_ok: bool = True
    degraded: bool = False             # the day's composite ran on < 7 inputs
    sparkline: list[SparkPoint] = []


class HealthFlag(DefaultsRequired):
    """A point-in-time health flag (oxygen / thermoregulation) with an 'unknown' state."""

    kind: FlagKind
    state: FlagState
    label: str
    value: float | None = None
    threshold_low: float | None = None
    threshold_high: float | None = None
    direction: str | None = None  # "low" | "above" | "below" when flagged
    recent: bool = False          # fired within the trailing 7 days
    tab_href: str


class StructuralGap(DefaultsRequired):
    """A contiguous SpO2 coverage gap, rendered as an explicit 'no data' span."""

    start: str
    end: str


class TrajectoryEvent(DefaultsRequired):
    """A sustained recovery regime detected from the score (low / elevated), for annotation."""

    start: str
    end: str
    kind: Literal["low", "elevated"]
    label: str


class CorrelationPoint(DefaultsRequired):
    """One point in a nightly-HRV-vs-other-metric scatter (consumed by the HRV tab)."""

    date: str
    hrv_nightly: float
    other_value: float


class MetricCorrelation(DefaultsRequired):
    """Correlation series between nightly HRV and another metric (HRV tab scatter)."""

    metric: str
    label: str
    points: list[CorrelationPoint] = []
    r_value: float | None = None
    sample_count: int = 0


class DashboardOverviewResponse(DefaultsRequired):
    """Latest recovery dashboard overview.

    `correlations` is not rendered on the overview itself; it is retained for the HRV
    detail tab, which reads it from this endpoint.
    """

    date: str
    state: RecoveryState = RecoveryState()
    score: list[RecoveryScorePoint] = []
    change: MeaningfulChange = MeaningfulChange()
    evidence: list[EvidenceRow] = []
    flags: list[HealthFlag] = []
    spo2_gaps: list[StructuralGap] = []
    events: list[TrajectoryEvent] = []
    correlations: list[MetricCorrelation] = []
