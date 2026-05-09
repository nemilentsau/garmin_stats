"""
Pydantic models for Garmin Stats — three tiers:

  Tier 1: Reading-level atoms (parser output)
  Tier 2: Day-level containers (parser output)
  Tier 3: API response models (match frontend TS interfaces)
"""

from typing import Literal

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)
from app.domains.routines.contracts import (
    CardLog,
    CardLogRangeResponse,
    CardLogStatus,
    CardLogStatusEntry,
    CardOverride,
    CardOverrideAction,
    CardTemplate,
    CardTemplatesResponse,
    RendererFamily,
    RoutineAssignment,
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
    ScheduleDay,
    ScheduleOccurrence,
    ScheduleOccurrenceSourceKind,
    ScheduleWindow,
    SlotName,
    TodayCard,
    TodayCardLogUpdateRequest,
    TodayResponse,
    TodaySlot,
    TodayStats,
    WeekdayName,
)

__all__ = [
    "CardLog",
    "CardLogRangeResponse",
    "CardLogStatus",
    "CardLogStatusEntry",
    "CardOverride",
    "CardOverrideAction",
    "CardTemplate",
    "CardTemplatesResponse",
    "EntityStatus",
    "RendererFamily",
    "RoutineAssignment",
    "RoutineAssignmentsResponse",
    "RoutineSchedule",
    "RoutineSchedulesResponse",
    "ScheduleDay",
    "ScheduleOccurrence",
    "ScheduleOccurrenceSourceKind",
    "ScheduleWindow",
    "SlotName",
    "TodayCard",
    "TodayCardLogUpdateRequest",
    "TodayResponse",
    "TodaySlot",
    "TodayStats",
    "WeekdayName",
]


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


class Goal(DefaultsRequired):
    id: str
    title: str
    description: str | None = None
    status: EntityStatus = "active"
    priority: int = 0
    tags: list[str] = []


class UserProfile(DefaultsRequired):
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


class Routine(DefaultsRequired):
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


class RoutineEntry(DefaultsRequired):
    id: str
    routine_id: str
    date: str
    timestamp_local: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    completion_state: RoutineEntryCompletionState = "completed"
    source: str = "manual"
    notes: str | None = None


class DailyCheckIn(DefaultsRequired):
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


class Note(DefaultsRequired):
    id: str
    date: str
    category: str
    title: str
    content: str
    tags: list[str] = []


OutcomeMetricDirection = Literal["higher_is_better", "lower_is_better"]
ExperimentDesignType = Literal["ab_intervention"]


class OutcomeMetric(DefaultsRequired):
    path: str
    direction: OutcomeMetricDirection = "higher_is_better"
    min_effect_size: float = 0.2


class ExperimentDesign(DefaultsRequired):
    type: ExperimentDesignType = "ab_intervention"
    baseline_start_date: str | None = None
    baseline_end_date: str | None = None
    treatment_start_date: str | None = None
    treatment_end_date: str | None = None
    baseline_duration_days: int | None = None
    expected_lag_days: list[int] = [0]
    min_adherence_pct: float = 0.70


class Experiment(DefaultsRequired):
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


class ExperimentExposure(DefaultsRequired):
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


class ExperimentMetricEffect(DefaultsRequired):
    metric: str
    baseline_value: float | None = None
    current_value: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None
    sample_count: int = 0


class ExperimentReport(DefaultsRequired):
    id: str
    experiment_id: str
    report_date: str
    summary: str | None = None
    confidence: ExperimentReportConfidence = "insufficient"
    confounders: list[str] = []
    effects: list[ExperimentMetricEffect] = []


class MetricLagResult(DefaultsRequired):
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


class MetricAnalysis(DefaultsRequired):
    path: str
    direction: str
    lag_results: list[MetricLagResult]
    best_lag: int
    best_result: MetricLagResult


class ConfounderCheck(DefaultsRequired):
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


class AdherenceDayEntry(DefaultsRequired):
    date: str
    state: ExperimentAdherenceState
    exposure_score: float | None = None


class ExperimentAnalysis(DefaultsRequired):
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


class ExperimentWithAnalysis(DefaultsRequired):
    experiment: Experiment
    analysis: ExperimentAnalysis | None = None


class ExperimentPreviewIssue(DefaultsRequired):
    level: Literal["error", "warning"]
    message: str


class ExperimentPreviewResponse(DefaultsRequired):
    valid: bool
    issues: list[ExperimentPreviewIssue] = []
    experiment: Experiment | None = None


class ExperimentAnalysisRefreshResponse(DefaultsRequired):
    refreshed: int


class Plan(DefaultsRequired):
    id: str
    title: str
    scope: str
    status: PlanStatus = "draft"
    source: str = "manual"
    goal: str | None = None
    markdown_body: str | None = None
    structured_outline_json: dict[str, object] = {}
    linked_experiment_ids: list[str] = []


class PlanItem(DefaultsRequired):
    id: str
    plan_id: str
    title: str
    date: str | None = None
    time_block: str | None = None
    instructions: str | None = None
    linked_routine_id: str | None = None
    completion_state: PlanItemCompletionState = "pending"
    completion_notes: str | None = None


class AssistantThread(DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"
    claude_session_id: str | None = None
    last_context_snapshot_id: str | None = None
    status: ThreadStatus = "active"
    last_message_at: str | None = None
    created_at: str | None = None


class AssistantMessage(DefaultsRequired):
    id: str
    thread_id: str
    role: AssistantMessageRole
    content_markdown: str
    structured_payload_json: dict[str, object] = {}
    evidence_refs_json: list[str] = []
    created_at: str | None = None


class AssistantRun(DefaultsRequired):
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


class ContextSnapshot(DefaultsRequired):
    id: str
    date_window_start: str | None = None
    date_window_end: str | None = None
    snapshot_json: dict[str, object] = {}
    summary_markdown: str | None = None
    created_at: str | None = None


class EvidenceCard(DefaultsRequired):
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


class TargetMetricDefinition(DefaultsRequired):
    key: str
    label: str
    path: str
    unit: str


class GoalsResponse(AutoTotalResponse, items_field="goals"):
    goals: list[Goal] = []
    total: int = 0


class RoutinesResponse(AutoTotalResponse, items_field="routines"):
    routines: list[Routine] = []
    total: int = 0


class RoutineEntriesResponse(AutoTotalResponse, items_field="entries"):
    entries: list[RoutineEntry] = []
    total: int = 0


class DailyCheckInsResponse(AutoTotalResponse, items_field="checkins"):
    checkins: list[DailyCheckIn] = []
    total: int = 0


class NotesResponse(AutoTotalResponse, items_field="notes"):
    notes: list[Note] = []
    total: int = 0


class ExperimentsResponse(AutoTotalResponse, items_field="experiments"):
    experiments: list[ExperimentWithAnalysis] = []
    total: int = 0


class TargetMetricsResponse(AutoTotalResponse, items_field="metrics"):
    metrics: list[TargetMetricDefinition] = []
    total: int = 0


AssistantArtifactKind = Literal["routine_spec", "card_template", "capability_request"]
AssistantArtifactStatus = Literal["draft", "validated", "invalid", "activated"]
ArtifactBundleItemKind = Literal["card_template", "routine_spec"]
ArtifactBundleDeltaAction = Literal["create", "update"]


class TimerSegmentSpec(StrictDefaultsRequired):
    label: str
    duration_seconds: int


class RatingPromptSpec(StrictDefaultsRequired):
    key: str
    label: str
    scale_min: int | None = None
    scale_max: int | None = None


class ChecklistItemSpec(StrictDefaultsRequired):
    id: str
    label: str
    detail: str | None = None


class ExerciseItemSpec(StrictDefaultsRequired):
    id: str
    label: str
    detail: str | None = None
    reps: str | None = None
    duration_seconds: int | None = None


class TimerSessionPayloadSpec(StrictDefaultsRequired):
    duration_minutes: int | None = None
    pattern: str | None = None
    instructions: str | None = None
    segments: list[TimerSegmentSpec] = []
    rating_prompts: list[RatingPromptSpec] = []


class ChecklistBlockPayloadSpec(StrictDefaultsRequired):
    instructions: str | None = None
    items: list[ChecklistItemSpec] = []


class ExerciseBlockPayloadSpec(StrictDefaultsRequired):
    instructions: str | None = None
    exercises: list[ExerciseItemSpec] = []


class CardTemplateSpec(StrictDefaultsRequired):
    id: str
    name: str
    renderer: RendererFamily
    slot_default: SlotName
    summary: str | None = None
    tags: list[str] = []
    payload: dict[str, object] = {}


class RoutineAssignmentSpec(StrictDefaultsRequired):
    id: str
    card_template_id: str
    day: int
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSpec(StrictDefaultsRequired):
    id: str
    name: str
    start_date: str
    end_date: str | None = None
    status: EntityStatus = "active"
    tags: list[str] = []
    notes: str | None = None
    assignments: list[RoutineAssignmentSpec] = []


class CapabilityRequestSpec(StrictDefaultsRequired):
    requested_renderer: str
    reason: str
    source_artifact_id: str | None = None
    payload_example_json: dict[str, object] = {}


class AssistantArtifact(DefaultsRequired):
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


class AssistantArtifactCreateRequest(StrictDefaultsRequired):
    id: str
    kind: AssistantArtifactKind
    schema_version: int
    source_thread_id: str | None = None
    source_snapshot_id: str | None = None
    payload_json: dict[str, object] = {}


class AssistantArtifactsResponse(AutoTotalResponse, items_field="artifacts"):
    artifacts: list[AssistantArtifact] = []
    total: int = 0


class ArtifactBundleSpec(StrictDefaultsRequired):
    id: str
    name: str
    schema_version: int = 1
    description: str | None = None
    card_templates: list[CardTemplateSpec] = []
    routine_specs: list[RoutineSpec] = []


class ArtifactBundleIssue(DefaultsRequired):
    path: str
    message: str
    blocking: bool = True


class ArtifactBundleDelta(DefaultsRequired):
    artifact_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    action: ArtifactBundleDeltaAction
    summary: str


class ArtifactBundlePreviewResponse(DefaultsRequired):
    bundle_id: str
    bundle_name: str
    valid: bool = False
    issues: list[ArtifactBundleIssue] = []
    deltas: list[ArtifactBundleDelta] = []


class ArtifactBundleImportResponse(DefaultsRequired):
    bundle_id: str
    bundle_name: str
    imported_artifact_ids: list[str] = []
    total_imported: int = 0
    deltas: list[ArtifactBundleDelta] = []


class AssistantThreadCreateRequest(DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"


class AssistantMessageCreateRequest(DefaultsRequired):
    id: str
    content: str


class AssistantThreadsResponse(AutoTotalResponse, items_field="threads"):
    threads: list[AssistantThread] = []
    total: int = 0


class AssistantMessagesResponse(AutoTotalResponse, items_field="messages"):
    messages: list[AssistantMessage] = []
    total: int = 0


class DaySummaryResponse(DefaultsRequired):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(AutoTotalResponse, items_field="days"):
    days: list[str]
    total: int = 0


# ---------------------------------------------------------------------------
# Program spec models
# ---------------------------------------------------------------------------


class Program(DefaultsRequired):
    id: str
    name: str
    version: int
    status: ProgramStatus = "active"
    spec: dict[str, object] = {}
    imported_at: str | None = None
    updated_at: str | None = None
    retired_at: str | None = None


class ProgramVersion(DefaultsRequired):
    program_id: str
    version: int
    spec: dict[str, object] = {}
    imported_at: str | None = None


class ProgramsResponse(AutoTotalResponse, items_field="programs"):
    programs: list[Program] = []
    total: int = 0


class ProgramVersionsResponse(AutoTotalResponse, items_field="versions"):
    versions: list[ProgramVersion] = []
    total: int = 0
