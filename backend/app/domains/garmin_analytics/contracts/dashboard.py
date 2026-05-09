"""Recovery dashboard overview response contracts."""

from app.contracts.base import DefaultsRequired


class ReadinessScore(DefaultsRequired):
    """Composite recovery readiness score and component explanations."""

    score: int | None = None
    components: dict[str, float] = {}
    component_hints: dict[str, str] = {}  # human-readable explanation per component
    label: str | None = None  # "Ready", "Moderate", "Rest"


class CorrelationPoint(DefaultsRequired):
    """One point in a dashboard metric correlation scatterplot."""

    date: str
    hrv_nightly: float
    other_value: float


class MetricCorrelation(DefaultsRequired):
    """Correlation series between nightly HRV and another dashboard metric."""

    metric: str              # "sleep_score", "resting_hr"
    label: str               # "Sleep Score", "Resting HR"
    points: list[CorrelationPoint] = []
    r_value: float | None = None
    sample_count: int = 0


class TodayVitals(DefaultsRequired):
    """Latest selected-day vitals shown in the recovery dashboard."""

    resting_hr: int | None = None
    resting_hr_delta_7d: float | None = None
    nightly_hrv: float | None = None
    nightly_hrv_delta_7d: float | None = None
    hrv_status: str | None = None
    sleep_score: int | None = None
    stress_avg: float | None = None


class SparklinePoint(DefaultsRequired):
    """One dated sparkline point with raw value and moving average."""

    date: str
    value: float | None = None
    ma7: float | None = None


class SparklineSummary(DefaultsRequired):
    """Summary stats for one dashboard sparkline series."""

    avg: float | None = None
    min: float | None = None
    max: float | None = None


class SparklineSeries(DefaultsRequired):
    """Dashboard sparkline points and summary stats for one metric."""

    points: list[SparklinePoint] = []
    summary: SparklineSummary = SparklineSummary()


class DashboardSparklines(DefaultsRequired):
    """All dashboard sparkline series."""

    resting_hr: SparklineSeries = SparklineSeries()
    nightly_hrv: SparklineSeries = SparklineSeries()
    sleep_score: SparklineSeries = SparklineSeries()
    stress_avg: SparklineSeries = SparklineSeries()


class DashboardOverviewResponse(DefaultsRequired):
    """Latest dashboard overview response."""

    date: str
    readiness: ReadinessScore | None = None
    vitals: TodayVitals | None = None
    sparklines: DashboardSparklines | None = None
    correlations: list[MetricCorrelation] = []
