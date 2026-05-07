"""
Pydantic models for Garmin Stats — three tiers:

  Tier 1: Reading-level atoms (parser output)
  Tier 2: Day-level containers (parser output)
  Tier 3: API response models (match frontend TS interfaces)
"""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, model_validator

# ---------------------------------------------------------------------------
# Garmin analytics contracts
# ---------------------------------------------------------------------------
from app.domains.garmin_analytics.contracts import (
    ActivityReading as ActivityReading,
)
from app.domains.garmin_analytics.contracts import (
    BodyBatteryAnalysisResponse as BodyBatteryAnalysisResponse,
)
from app.domains.garmin_analytics.contracts import (
    BodyBatteryReading as BodyBatteryReading,
)
from app.domains.garmin_analytics.contracts import (
    BodyBatteryTrendPoint as BodyBatteryTrendPoint,
)
from app.domains.garmin_analytics.contracts import (
    CircadianHRPoint as CircadianHRPoint,
)
from app.domains.garmin_analytics.contracts import (
    CorrelationPoint as CorrelationPoint,
)
from app.domains.garmin_analytics.contracts import (
    DailyAggregatesResponse as DailyAggregatesResponse,
)
from app.domains.garmin_analytics.contracts import (
    DailyAvgHRTrendPoint as DailyAvgHRTrendPoint,
)
from app.domains.garmin_analytics.contracts import (
    DailyBodyBatteryStats as DailyBodyBatteryStats,
)
from app.domains.garmin_analytics.contracts import (
    DailyHeartRateStats as DailyHeartRateStats,
)
from app.domains.garmin_analytics.contracts import (
    DailyHrvStats as DailyHrvStats,
)
from app.domains.garmin_analytics.contracts import (
    DailyMetric as DailyMetric,
)
from app.domains.garmin_analytics.contracts import (
    DailyMetricStats as DailyMetricStats,
)
from app.domains.garmin_analytics.contracts import (
    DailySkinTempStats as DailySkinTempStats,
)
from app.domains.garmin_analytics.contracts import (
    DailySleepStats as DailySleepStats,
)
from app.domains.garmin_analytics.contracts import (
    DashboardOverviewResponse as DashboardOverviewResponse,
)
from app.domains.garmin_analytics.contracts import (
    DashboardSparklines as DashboardSparklines,
)
from app.domains.garmin_analytics.contracts import (
    DayData as DayData,
)
from app.domains.garmin_analytics.contracts import (
    DayHrv as DayHrv,
)
from app.domains.garmin_analytics.contracts import (
    DaySkinTemp as DaySkinTemp,
)
from app.domains.garmin_analytics.contracts import (
    DaySleep as DaySleep,
)
from app.domains.garmin_analytics.contracts import (
    DayWellness as DayWellness,
)
from app.domains.garmin_analytics.contracts import (
    HeartRateAnalysisResponse as HeartRateAnalysisResponse,
)
from app.domains.garmin_analytics.contracts import (
    HeartRateDataQuality as HeartRateDataQuality,
)
from app.domains.garmin_analytics.contracts import (
    HeartRateInsight as HeartRateInsight,
)
from app.domains.garmin_analytics.contracts import (
    HeartRateInsightsResponse as HeartRateInsightsResponse,
)
from app.domains.garmin_analytics.contracts import (
    HeartRateReading as HeartRateReading,
)
from app.domains.garmin_analytics.contracts import (
    HeartRateRecovery as HeartRateRecovery,
)
from app.domains.garmin_analytics.contracts import (
    HRDistributionResponse as HRDistributionResponse,
)
from app.domains.garmin_analytics.contracts import (
    HRHistogramBin as HRHistogramBin,
)
from app.domains.garmin_analytics.contracts import (
    HRPatternWindow as HRPatternWindow,
)
from app.domains.garmin_analytics.contracts import (
    HrvAnalysisResponse as HrvAnalysisResponse,
)
from app.domains.garmin_analytics.contracts import (
    HrvBaselineBands as HrvBaselineBands,
)
from app.domains.garmin_analytics.contracts import (
    HrvDataQuality as HrvDataQuality,
)
from app.domains.garmin_analytics.contracts import (
    HrvDayOfWeekBucket as HrvDayOfWeekBucket,
)
from app.domains.garmin_analytics.contracts import (
    HrvDistribution as HrvDistribution,
)
from app.domains.garmin_analytics.contracts import (
    HrvDistributionBin as HrvDistributionBin,
)
from app.domains.garmin_analytics.contracts import (
    HrvInsight as HrvInsight,
)
from app.domains.garmin_analytics.contracts import (
    HrvInsightsResponse as HrvInsightsResponse,
)
from app.domains.garmin_analytics.contracts import (
    HrvIntradaySegment as HrvIntradaySegment,
)
from app.domains.garmin_analytics.contracts import (
    HrvLongBaseline as HrvLongBaseline,
)
from app.domains.garmin_analytics.contracts import (
    HrvPatternWindow as HrvPatternWindow,
)
from app.domains.garmin_analytics.contracts import (
    HrvRecovery as HrvRecovery,
)
from app.domains.garmin_analytics.contracts import (
    HrvResponse as HrvResponse,
)
from app.domains.garmin_analytics.contracts import (
    HrvStatusBucket as HrvStatusBucket,
)
from app.domains.garmin_analytics.contracts import (
    HrvStreak as HrvStreak,
)
from app.domains.garmin_analytics.contracts import (
    HrvSummary as HrvSummary,
)
from app.domains.garmin_analytics.contracts import (
    HrvTrajectory as HrvTrajectory,
)
from app.domains.garmin_analytics.contracts import (
    HrvTrendBand as HrvTrendBand,
)
from app.domains.garmin_analytics.contracts import (
    HrvValue as HrvValue,
)
from app.domains.garmin_analytics.contracts import (
    HRZoneBucket as HRZoneBucket,
)
from app.domains.garmin_analytics.contracts import (
    HRZoneDuration as HRZoneDuration,
)
from app.domains.garmin_analytics.contracts import (
    MetricCorrelation as MetricCorrelation,
)
from app.domains.garmin_analytics.contracts import (
    NightlyHrvTrendPoint as NightlyHrvTrendPoint,
)
from app.domains.garmin_analytics.contracts import (
    PeriodBodyBatteryStats as PeriodBodyBatteryStats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodHeartRateStats as PeriodHeartRateStats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodHrvStats as PeriodHrvStats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodMetricStats as PeriodMetricStats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodSkinTempStats as PeriodSkinTempStats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodSleepStats as PeriodSleepStats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodSpo2Stats as PeriodSpo2Stats,
)
from app.domains.garmin_analytics.contracts import (
    PeriodSummary as PeriodSummary,
)
from app.domains.garmin_analytics.contracts import (
    ReadinessScore as ReadinessScore,
)
from app.domains.garmin_analytics.contracts import (
    RespirationReading as RespirationReading,
)
from app.domains.garmin_analytics.contracts import (
    RestingHRReading as RestingHRReading,
)
from app.domains.garmin_analytics.contracts import (
    RestingHRTrendPoint as RestingHRTrendPoint,
)
from app.domains.garmin_analytics.contracts import (
    SkinTempOvernight as SkinTempOvernight,
)
from app.domains.garmin_analytics.contracts import (
    SkinTempResponse as SkinTempResponse,
)
from app.domains.garmin_analytics.contracts import (
    SleepAnalysisResponse as SleepAnalysisResponse,
)
from app.domains.garmin_analytics.contracts import (
    SleepAssessment as SleepAssessment,
)
from app.domains.garmin_analytics.contracts import (
    SleepingHRPoint as SleepingHRPoint,
)
from app.domains.garmin_analytics.contracts import (
    SleepLevel as SleepLevel,
)
from app.domains.garmin_analytics.contracts import (
    SleepResponse as SleepResponse,
)
from app.domains.garmin_analytics.contracts import (
    SleepTrendPoint as SleepTrendPoint,
)
from app.domains.garmin_analytics.contracts import (
    SparklinePoint as SparklinePoint,
)
from app.domains.garmin_analytics.contracts import (
    SparklineSeries as SparklineSeries,
)
from app.domains.garmin_analytics.contracts import (
    SparklineSummary as SparklineSummary,
)
from app.domains.garmin_analytics.contracts import (
    SpO2Reading as SpO2Reading,
)
from app.domains.garmin_analytics.contracts import (
    StepsReading as StepsReading,
)
from app.domains.garmin_analytics.contracts import (
    StressAnalysisResponse as StressAnalysisResponse,
)
from app.domains.garmin_analytics.contracts import (
    StressReading as StressReading,
)
from app.domains.garmin_analytics.contracts import (
    StressTrendPoint as StressTrendPoint,
)
from app.domains.garmin_analytics.contracts import (
    TodayVitals as TodayVitals,
)
from app.domains.garmin_analytics.contracts import (
    WeeklyBodyBatteryBox as WeeklyBodyBatteryBox,
)
from app.domains.garmin_analytics.contracts import (
    WeeklyHrvBox as WeeklyHrvBox,
)
from app.domains.garmin_analytics.contracts import (
    WeeklyRestingHRBox as WeeklyRestingHRBox,
)
from app.domains.garmin_analytics.contracts import (
    WeeklySleepBox as WeeklySleepBox,
)
from app.domains.garmin_analytics.contracts import (
    WeeklyStressBox as WeeklyStressBox,
)
from app.domains.garmin_analytics.contracts import (
    WellnessResponse as WellnessResponse,
)


class _DefaultsRequired(BaseModel):
    """Base for models where all fields (even those with defaults) should appear
    as 'required' in the JSON schema serialization output.  This ensures
    openapi-typescript generates `prop: T | null` instead of `prop?: T | null`."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class _AutoTotalResponse(_DefaultsRequired):
    """Response base that auto-computes ``total`` from the items list field.

    Subclasses declare which field holds the items via ``__init_subclass__``:

        class FoosResponse(_AutoTotalResponse, items_field="foos"):
            foos: list[Foo] = []
            total: int = 0

    If ``total`` is supplied explicitly it is respected; otherwise it is set
    to ``len(items_field)``.
    """

    _items_field: ClassVar[str]

    def __init_subclass__(cls, items_field: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if items_field:
            cls._items_field = items_field

    @model_validator(mode="before")
    @classmethod
    def _auto_fill_total(cls, data: Any) -> Any:
        if isinstance(data, dict) and "total" not in data:
            items = data.get(cls._items_field)
            if isinstance(items, list):
                data["total"] = len(items)
        return data


class _StrictDefaultsRequired(_DefaultsRequired):
    """Base for models that must reject unknown keys."""

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
    )


# ---------------------------------------------------------------------------
# Shared Literal type aliases
# ---------------------------------------------------------------------------

EntityStatus = Literal["active", "retired", "paused"]
ExperimentStatus = Literal["draft", "active", "completed"]
PlanStatus = Literal["draft", "active", "completed"]
ProgramStatus = Literal["active", "retired"]
ThreadStatus = Literal["active", "archived"]
PlanItemCompletionState = Literal["pending", "in_progress", "completed", "skipped"]
RoutineEntryCompletionState = Literal["completed", "partial", "skipped"]
ExperimentAdherenceState = Literal["full", "partial", "missed", "completed", "unknown"]
ExperimentReportConfidence = Literal["insufficient", "low", "moderate", "high"]
EvidenceConfidence = Literal["insufficient", "low", "moderate", "high"]
AssistantMessageRole = Literal["user", "assistant", "system"]
AssistantRunStatus = Literal["running", "completed", "failed"]
AssistantRunTaskType = Literal["chat", "analysis", "planning"]


# ---------------------------------------------------------------------------
# Health assistant foundation models
# ---------------------------------------------------------------------------


DEFAULT_PROFILE_ID = "default"


class Goal(_DefaultsRequired):
    id: str
    title: str
    description: str | None = None
    status: EntityStatus = "active"
    priority: int = 0
    tags: list[str] = []


class UserProfile(_DefaultsRequired):
    id: str = DEFAULT_PROFILE_ID
    name: str | None = None
    birth_year: int | None = None
    age_range: str | None = None
    sex: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    primary_goals: list[str] = []
    constraints: list[str] = []
    injuries: list[str] = []
    equipment: list[str] = []
    default_weekly_schedule: list[str] = []
    sleep_constraints: list[str] = []
    nutrition_preferences: list[str] = []
    coaching_style_preferences: list[str] = []


class Routine(_DefaultsRequired):
    id: str
    name: str
    category: str
    status: EntityStatus = "active"
    description: str | None = None
    default_unit: str = "boolean"
    target_frequency: str | None = None
    default_time_of_day: str | None = None
    tags: list[str] = []
    linked_goal_ids: list[str] = []


class RoutineEntry(_DefaultsRequired):
    id: str
    routine_id: str
    date: str
    timestamp_local: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    completion_state: RoutineEntryCompletionState = "completed"
    source: str = "manual"
    notes: str | None = None


class DailyCheckIn(_DefaultsRequired):
    id: str
    date: str
    energy: int | None = None
    mood: int | None = None
    motivation: int | None = None
    soreness: int | None = None
    stress_subjective: int | None = None
    sleep_quality_subjective: int | None = None
    workload_subjective: int | None = None
    illness_flag: bool = False
    travel_flag: bool = False
    alcohol_flag: bool = False
    notes: str | None = None


class Note(_DefaultsRequired):
    id: str
    date: str
    category: str
    title: str
    content: str
    tags: list[str] = []


OutcomeMetricDirection = Literal["higher_is_better", "lower_is_better"]
ExperimentDesignType = Literal["ab_intervention"]


class OutcomeMetric(_DefaultsRequired):
    path: str
    direction: OutcomeMetricDirection = "higher_is_better"
    min_effect_size: float = 0.2


class ExperimentDesign(_DefaultsRequired):
    type: ExperimentDesignType = "ab_intervention"
    baseline_start_date: str | None = None
    baseline_end_date: str | None = None
    treatment_start_date: str | None = None
    treatment_end_date: str | None = None
    baseline_duration_days: int | None = None
    expected_lag_days: list[int] = [0]
    min_adherence_pct: float = 0.70


class Experiment(_DefaultsRequired):
    id: str
    name: str
    status: ExperimentStatus = "draft"
    goal: str | None = None
    hypothesis: str | None = None
    design: ExperimentDesign | None = None
    linked_routine_ids: list[str] = []
    outcome_metrics: list[OutcomeMetric] = []
    confounder_watch: list[str] = []
    confounder_notes: str | None = None
    expected_lag_days: list[int] = []
    priority: int = 0


class ExperimentExposure(_DefaultsRequired):
    id: str
    experiment_id: str
    date: str
    exposure_score: float | None = None
    adherence_state: ExperimentAdherenceState = "unknown"
    linked_routine_entry_ids: list[str] = []
    notes: str | None = None

    @staticmethod
    def auto_id(experiment_id: str, date: str) -> str:
        return f"exposure:auto:{experiment_id}:{date}"


class ExperimentMetricEffect(_DefaultsRequired):
    metric: str
    baseline_value: float | None = None
    current_value: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None
    sample_count: int = 0


class ExperimentReport(_DefaultsRequired):
    id: str
    experiment_id: str
    report_date: str
    summary: str | None = None
    confidence: ExperimentReportConfidence = "insufficient"
    confounders: list[str] = []
    effects: list[ExperimentMetricEffect] = []


class MetricLagResult(_DefaultsRequired):
    lag_days: int
    treatment_start_effective: str
    baseline_mean: float
    baseline_sd: float
    baseline_n: int
    treatment_mean: float
    treatment_sd: float
    treatment_n: int
    delta_abs: float
    delta_pct: float
    cohens_d: float
    hedges_g: float
    nap: float
    nap_interpretation: str
    p_value_permutation: float
    p_value_welch: float
    baseline_trend_slope: float
    baseline_trend_p: float
    autocorrelation_lag1_baseline: float
    autocorrelation_lag1_treatment: float
    direction_correct: bool


class MetricAnalysis(_DefaultsRequired):
    path: str
    direction: str
    lag_results: list[MetricLagResult]
    best_lag: int
    best_result: MetricLagResult


class ConfounderCheck(_DefaultsRequired):
    path: str
    source: str
    baseline_mean: float | None = None
    treatment_mean: float | None = None
    delta_pct: float | None = None
    is_significant: bool = False
    note: str = ""
    baseline_flag_days: int | None = None
    treatment_flag_days: int | None = None
    baseline_total_days: int | None = None
    treatment_total_days: int | None = None


class AdherenceDayEntry(_DefaultsRequired):
    date: str
    state: ExperimentAdherenceState
    exposure_score: float | None = None


class ExperimentAnalysis(_DefaultsRequired):
    experiment_id: str
    analysis_date: str
    phase: str
    days_in_baseline: int
    days_in_treatment: int
    adherence_rate: float
    adherence_by_day: list[AdherenceDayEntry]
    metrics: list[MetricAnalysis]
    confounders: list[ConfounderCheck]
    overall_confidence: ExperimentReportConfidence
    summary: str


class ExperimentWithAnalysis(_DefaultsRequired):
    experiment: Experiment
    analysis: ExperimentAnalysis | None = None


class ExperimentPreviewIssue(_DefaultsRequired):
    level: Literal["error", "warning"]
    message: str


class ExperimentPreviewResponse(_DefaultsRequired):
    valid: bool
    issues: list[ExperimentPreviewIssue] = []
    experiment: Experiment | None = None


class ExperimentAnalysisRefreshResponse(_DefaultsRequired):
    refreshed: int


class Plan(_DefaultsRequired):
    id: str
    title: str
    scope: str
    status: PlanStatus = "draft"
    source: str = "manual"
    goal: str | None = None
    markdown_body: str | None = None
    structured_outline_json: dict[str, object] = {}
    linked_experiment_ids: list[str] = []


class PlanItem(_DefaultsRequired):
    id: str
    plan_id: str
    title: str
    date: str | None = None
    time_block: str | None = None
    instructions: str | None = None
    linked_routine_id: str | None = None
    completion_state: PlanItemCompletionState = "pending"
    completion_notes: str | None = None


class AssistantThread(_DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"
    claude_session_id: str | None = None
    last_context_snapshot_id: str | None = None
    status: ThreadStatus = "active"
    last_message_at: str | None = None
    created_at: str | None = None


class AssistantMessage(_DefaultsRequired):
    id: str
    thread_id: str
    role: AssistantMessageRole
    content_markdown: str
    structured_payload_json: dict[str, object] = {}
    evidence_refs_json: list[str] = []
    created_at: str | None = None


class AssistantRun(_DefaultsRequired):
    id: str
    task_type: AssistantRunTaskType
    status: AssistantRunStatus
    thread_id: str | None = None
    context_snapshot_id: str | None = None
    claude_session_id: str | None = None
    command_json: dict[str, object] = {}
    stdout_path: str | None = None
    stderr_path: str | None = None
    usage_json: dict[str, object] = {}
    started_at: str | None = None
    finished_at: str | None = None


class ContextSnapshot(_DefaultsRequired):
    id: str
    date_window_start: str | None = None
    date_window_end: str | None = None
    snapshot_json: dict[str, object] = {}
    summary_markdown: str | None = None
    created_at: str | None = None


class EvidenceCard(_DefaultsRequired):
    id: str
    kind: str
    title: str
    summary: str
    metric: str | None = None
    window: str | None = None
    sample_count: int = 0
    confidence: EvidenceConfidence = "insufficient"
    caveats: list[str] = []
    payload_json: dict[str, object] = {}


class TargetMetricDefinition(_DefaultsRequired):
    key: str
    label: str
    path: str
    unit: str


class GoalsResponse(_AutoTotalResponse, items_field="goals"):
    goals: list[Goal] = []
    total: int = 0


class RoutinesResponse(_AutoTotalResponse, items_field="routines"):
    routines: list[Routine] = []
    total: int = 0


class RoutineEntriesResponse(_AutoTotalResponse, items_field="entries"):
    entries: list[RoutineEntry] = []
    total: int = 0


class DailyCheckInsResponse(_AutoTotalResponse, items_field="checkins"):
    checkins: list[DailyCheckIn] = []
    total: int = 0


class NotesResponse(_AutoTotalResponse, items_field="notes"):
    notes: list[Note] = []
    total: int = 0


class ExperimentsResponse(_AutoTotalResponse, items_field="experiments"):
    experiments: list[ExperimentWithAnalysis] = []
    total: int = 0


class TargetMetricsResponse(_AutoTotalResponse, items_field="metrics"):
    metrics: list[TargetMetricDefinition] = []
    total: int = 0


RendererFamily = Literal["timer_session", "checklist_block", "exercise_block"]
SlotName = Literal["morning", "midday", "evening", "anytime"]
WeekdayName = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
AssistantArtifactKind = Literal["routine_spec", "card_template", "capability_request"]
AssistantArtifactStatus = Literal["draft", "validated", "invalid", "activated"]
ArtifactBundleItemKind = Literal["card_template", "routine_spec"]
ArtifactBundleDeltaAction = Literal["create", "update"]
CardLogStatus = Literal["pending", "completed", "partial", "skipped"]
CardOverrideAction = Literal["add", "hide", "replace"]
ScheduleOccurrenceSourceKind = Literal["scheduled", "override_add", "override_replace"]


class TimerSegmentSpec(_StrictDefaultsRequired):
    label: str
    duration_seconds: int


class RatingPromptSpec(_StrictDefaultsRequired):
    key: str
    label: str
    scale_min: int | None = None
    scale_max: int | None = None


class ChecklistItemSpec(_StrictDefaultsRequired):
    id: str
    label: str
    detail: str | None = None


class ExerciseItemSpec(_StrictDefaultsRequired):
    id: str
    label: str
    detail: str | None = None
    reps: str | None = None
    duration_seconds: int | None = None


class TimerSessionPayloadSpec(_StrictDefaultsRequired):
    duration_minutes: int | None = None
    pattern: str | None = None
    instructions: str | None = None
    segments: list[TimerSegmentSpec] = []
    rating_prompts: list[RatingPromptSpec] = []


class ChecklistBlockPayloadSpec(_StrictDefaultsRequired):
    instructions: str | None = None
    items: list[ChecklistItemSpec] = []


class ExerciseBlockPayloadSpec(_StrictDefaultsRequired):
    instructions: str | None = None
    exercises: list[ExerciseItemSpec] = []


class CardTemplateSpec(_StrictDefaultsRequired):
    id: str
    name: str
    renderer: RendererFamily
    slot_default: SlotName
    summary: str | None = None
    tags: list[str] = []
    payload: dict[str, object] = {}


class RoutineAssignmentSpec(_StrictDefaultsRequired):
    id: str
    card_template_id: str
    day: int
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSpec(_StrictDefaultsRequired):
    id: str
    name: str
    start_date: str
    end_date: str | None = None
    status: EntityStatus = "active"
    tags: list[str] = []
    notes: str | None = None
    assignments: list[RoutineAssignmentSpec] = []


class CapabilityRequestSpec(_StrictDefaultsRequired):
    requested_renderer: str
    reason: str
    source_artifact_id: str | None = None
    payload_example_json: dict[str, object] = {}


class AssistantArtifact(_DefaultsRequired):
    id: str
    kind: AssistantArtifactKind
    schema_version: int
    status: AssistantArtifactStatus = "draft"
    source_thread_id: str | None = None
    source_snapshot_id: str | None = None
    payload_json: dict[str, object] = {}
    validation_errors: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None


class AssistantArtifactCreateRequest(_StrictDefaultsRequired):
    id: str
    kind: AssistantArtifactKind
    schema_version: int
    source_thread_id: str | None = None
    source_snapshot_id: str | None = None
    payload_json: dict[str, object] = {}


class AssistantArtifactsResponse(_AutoTotalResponse, items_field="artifacts"):
    artifacts: list[AssistantArtifact] = []
    total: int = 0


class ArtifactBundleSpec(_StrictDefaultsRequired):
    id: str
    name: str
    schema_version: int = 1
    description: str | None = None
    card_templates: list[CardTemplateSpec] = []
    routine_specs: list[RoutineSpec] = []


class ArtifactBundleIssue(_DefaultsRequired):
    path: str
    message: str
    blocking: bool = True


class ArtifactBundleDelta(_DefaultsRequired):
    artifact_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    action: ArtifactBundleDeltaAction
    summary: str


class ArtifactBundlePreviewResponse(_DefaultsRequired):
    bundle_id: str
    bundle_name: str
    valid: bool = False
    issues: list[ArtifactBundleIssue] = []
    deltas: list[ArtifactBundleDelta] = []


class ArtifactBundleImportResponse(_DefaultsRequired):
    bundle_id: str
    bundle_name: str
    imported_artifact_ids: list[str] = []
    total_imported: int = 0
    deltas: list[ArtifactBundleDelta] = []


class CardTemplate(_DefaultsRequired):
    id: str
    name: str
    renderer: RendererFamily
    slot_default: SlotName
    status: EntityStatus = "active"
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    source_artifact_id: str | None = None


class CardTemplatesResponse(_AutoTotalResponse, items_field="cards"):
    cards: list[CardTemplate] = []
    total: int = 0


class RoutineSchedule(_DefaultsRequired):
    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None


class RoutineAssignment(_DefaultsRequired):
    id: str
    routine_id: str
    card_template_id: str
    date: str
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSchedulesResponse(_AutoTotalResponse, items_field="routines"):
    routines: list[RoutineSchedule] = []
    total: int = 0


class RoutineAssignmentsResponse(_AutoTotalResponse, items_field="assignments"):
    assignments: list[RoutineAssignment] = []
    total: int = 0


class CardLog(_DefaultsRequired):
    id: str
    date: str
    occurrence_key: str
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class CardOverride(_DefaultsRequired):
    id: str
    date: str
    action: CardOverrideAction
    target_occurrence_key: str | None = None
    card_template_id: str | None = None
    slot: SlotName | None = None
    position: int | None = None
    notes: str | None = None


class TodayCardLogUpdateRequest(_StrictDefaultsRequired):
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "completed"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodayStats(_DefaultsRequired):
    total: int = 0
    completed: int = 0
    partial: int = 0
    skipped: int = 0
    pending: int = 0


class TodayCard(_DefaultsRequired):
    occurrence_key: str
    date: str
    slot: SlotName
    position: int = 0
    source_kind: ScheduleOccurrenceSourceKind
    schedule_override_action: CardOverrideAction | None = None
    target_occurrence_key: str | None = None
    routine_id: str | None = None
    routine_name: str | None = None
    assignment_id: str | None = None
    card_template_id: str
    name: str
    renderer: RendererFamily
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodaySlot(_DefaultsRequired):
    slot: SlotName
    label: str
    cards: list[TodayCard] = []


class TodayResponse(_DefaultsRequired):
    date: str
    stats: TodayStats
    slots: list[TodaySlot] = []


class CardLogStatusEntry(_DefaultsRequired):
    """Lightweight completion status for a single card occurrence."""
    occurrence_key: str
    status: CardLogStatus


class CardLogRangeResponse(_DefaultsRequired):
    """Completion statuses for a date range of card occurrences."""
    start_date: str
    end_date: str
    entries: list[CardLogStatusEntry] = []


class ScheduleOccurrence(_DefaultsRequired):
    occurrence_key: str
    date: str
    slot: SlotName
    position: int = 0
    source_kind: ScheduleOccurrenceSourceKind = "scheduled"
    schedule_override_action: CardOverrideAction | None = None
    target_occurrence_key: str | None = None
    routine_id: str | None = None
    routine_name: str | None = None
    assignment_id: str | None = None
    card_template_id: str
    name: str
    renderer: RendererFamily
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}


class ScheduleDay(_DefaultsRequired):
    date: str
    weekday: WeekdayName
    occurrences: list[ScheduleOccurrence] = []


class ScheduleWindow(_DefaultsRequired):
    start_date: str
    end_date: str
    days: list[ScheduleDay] = []


class AssistantThreadCreateRequest(_DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"


class AssistantMessageCreateRequest(_DefaultsRequired):
    id: str
    content: str


class AssistantThreadsResponse(_AutoTotalResponse, items_field="threads"):
    threads: list[AssistantThread] = []
    total: int = 0


class AssistantMessagesResponse(_AutoTotalResponse, items_field="messages"):
    messages: list[AssistantMessage] = []
    total: int = 0


class DaySummaryResponse(_DefaultsRequired):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(_AutoTotalResponse, items_field="days"):
    days: list[str]
    total: int = 0


# ---------------------------------------------------------------------------
# Program spec models
# ---------------------------------------------------------------------------


class Program(_DefaultsRequired):
    id: str
    name: str
    version: int
    status: ProgramStatus = "active"
    spec: dict[str, object] = {}
    imported_at: str | None = None
    updated_at: str | None = None
    retired_at: str | None = None


class ProgramVersion(_DefaultsRequired):
    program_id: str
    version: int
    spec: dict[str, object] = {}
    imported_at: str | None = None


class ProgramsResponse(_AutoTotalResponse, items_field="programs"):
    programs: list[Program] = []
    total: int = 0


class ProgramVersionsResponse(_AutoTotalResponse, items_field="versions"):
    versions: list[ProgramVersion] = []
    total: int = 0
