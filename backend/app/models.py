"""
Pydantic models for Garmin Stats — three tiers:

  Tier 1: Reading-level atoms (parser output)
  Tier 2: Day-level containers (parser output)
  Tier 3: API response models (match frontend TS interfaces)
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _DefaultsRequired(BaseModel):
    """Base for models where all fields (even those with defaults) should appear
    as 'required' in the JSON schema serialization output.  This ensures
    openapi-typescript generates `prop: T | null` instead of `prop?: T | null`."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class _StrictDefaultsRequired(_DefaultsRequired):
    """Base for models that must reject unknown keys."""

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
    )


# ---------------------------------------------------------------------------
# Tier 1 — Reading-level models
# ---------------------------------------------------------------------------

class HeartRateReading(_DefaultsRequired):
    timestamp: str | None = None
    value: int


class StressReading(_DefaultsRequired):
    timestamp: str | None = None
    value: int


class BodyBatteryReading(_DefaultsRequired):
    timestamp: str | None = None
    value: int


class SpO2Reading(_DefaultsRequired):
    timestamp: str | None = None
    value: int
    confidence: int | None = None
    mode: str


class RespirationReading(_DefaultsRequired):
    timestamp: str | None = None
    value: float


class ActivityReading(_DefaultsRequired):
    timestamp: str | None = None
    activity_type: str
    intensity: int | None = None
    steps: int | None = None
    calories: int | None = None
    distance: float | None = None


class StepsReading(_DefaultsRequired):
    timestamp: str | None = None
    steps: int
    distance: float | None = None
    calories: int | None = None


class RestingHRReading(_DefaultsRequired):
    timestamp: str | None = None
    resting_hr: int | None = None
    current_day_resting_hr: int | None = None


class SleepLevel(_DefaultsRequired):
    date: str
    timestamp: str | None = None
    level: str


class SleepAssessment(_DefaultsRequired):
    date: str
    overall_score: int | None = None
    deep_sleep_score: int | None = None
    light_sleep_score: int | None = None
    rem_sleep_score: int | None = None
    awake_time_score: int | None = None
    awakenings_count: int | None = None
    average_stress: float | None = None


class HrvValue(_DefaultsRequired):
    date: str
    timestamp: str | None = None
    value: float


class HrvSummary(_DefaultsRequired):
    date: str
    weekly_average: float | None = None
    last_night_average: float | None = None
    last_night_5_min_high: float | None = None
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    status: str


class SkinTempOvernight(_DefaultsRequired):
    date: str
    timestamp: str | None = None
    local_timestamp: float | None = None
    nightly_value: float | None = None
    average_deviation: float | None = None
    average_7_day_deviation: float | None = None


# ---------------------------------------------------------------------------
# Tier 2 — Day-level containers
# ---------------------------------------------------------------------------

class DayWellness(_DefaultsRequired):
    date: str
    heart_rate: list[HeartRateReading] = []
    stress: list[StressReading] = []
    body_battery: list[BodyBatteryReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps_summary: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []


class DaySleep(_DefaultsRequired):
    date: str
    sleep_levels: list[SleepLevel] = []
    sleep_assessments: list[SleepAssessment] = []


class DayHrv(_DefaultsRequired):
    date: str
    hrv_values: list[HrvValue] = []
    hrv_summaries: list[HrvSummary] = []


class DaySkinTemp(_DefaultsRequired):
    date: str
    skin_temp_overnight: list[SkinTempOvernight] = []


class DayData(_DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    wellness: DayWellness
    sleep: DaySleep
    hrv: DayHrv
    skin_temp: DaySkinTemp


# ---------------------------------------------------------------------------
# Tier 3 — API response models (match frontend TypeScript interfaces)
# ---------------------------------------------------------------------------

class WellnessResponse(_DefaultsRequired):
    days: list[str]
    heart_rate: list[HeartRateReading]
    stress: list[StressReading]
    body_battery: list[BodyBatteryReading]
    spo2: list[SpO2Reading]
    respiration: list[RespirationReading]
    activity: list[ActivityReading]
    steps_summary: list[StepsReading]
    resting_hr: list[RestingHRReading]


class SleepResponse(_DefaultsRequired):
    days: list[str]
    sleep_levels: list[SleepLevel]
    sleep_assessments: list[SleepAssessment]


class HrvResponse(_DefaultsRequired):
    days: list[str]
    hrv_values: list[HrvValue]
    hrv_summaries: list[HrvSummary]


class SkinTempResponse(_DefaultsRequired):
    days: list[str]
    skin_temp_overnight: list[SkinTempOvernight]


# Daily aggregate sub-models


class HRZoneBucket(_DefaultsRequired):
    label: str
    min_bpm: int
    max_bpm: int | None = None
    count: int
    pct: float


class DailyHeartRateStats(_DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    resting: int | None = None
    zones: list[HRZoneBucket] = []


class HeartRateRecovery(_DefaultsRequired):
    baseline_resting_7d: float | None = None
    delta_from_baseline: float | None = None
    status: str | None = None


class HeartRateDataQuality(_DefaultsRequired):
    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HRZoneDuration(_DefaultsRequired):
    label: str
    min_bpm: int
    max_bpm: int | None = None
    minutes: float
    pct: float


class HeartRateInsight(_DefaultsRequired):
    level: str
    title: str
    detail: str


class HeartRateInsightsResponse(_DefaultsRequired):
    date: str
    day_stats: DailyHeartRateStats
    recovery: HeartRateRecovery
    zones: list[HRZoneDuration]
    quality: HeartRateDataQuality
    insights: list[HeartRateInsight] = []


class DailyMetricStats(_DefaultsRequired):
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyBodyBatteryStats(_DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyHrvStats(_DefaultsRequired):
    weekly_avg: float | None = None
    nightly_avg: float | None = None
    status: str | None = None


class HrvRecovery(_DefaultsRequired):
    baseline_nightly_7d: float | None = None
    delta_nightly_from_baseline: float | None = None
    acute_gap_vs_weekly: float | None = None
    status: str | None = None


class HrvDataQuality(_DefaultsRequired):
    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HrvIntradaySegment(_DefaultsRequired):
    key: str
    label: str
    sample_count: int = 0
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    stdev: float | None = None
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None
    values: list[HrvValue] = []


class HrvStatusBucket(_DefaultsRequired):
    label: str
    count: int
    pct: float


class HrvTrendBand(_DefaultsRequired):
    nightly_typical_low: float | None = None
    nightly_typical_high: float | None = None


class HrvStreak(_DefaultsRequired):
    current_status: str | None = None
    streak_days: int = 0
    worst_recent_streak: int = 0


class HrvLongBaseline(_DefaultsRequired):
    baseline_30d: float | None = None
    delta_7d_vs_30d: float | None = None


class HrvBaselineBands(_DefaultsRequired):
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    five_min_high: float | None = None


class HrvDistributionBin(_DefaultsRequired):
    bin_start: float
    bin_end: float
    count: int


class HrvDistribution(_DefaultsRequired):
    bins: list[HrvDistributionBin] = []
    total_days: int = 0
    selected_value: float | None = None
    selected_percentile: float | None = None


class HrvTrajectory(_DefaultsRequired):
    early_avg: float | None = None
    mid_avg: float | None = None
    late_avg: float | None = None
    direction: str | None = None  # "rising", "falling", "flat", or None


class HrvDayOfWeekBucket(_DefaultsRequired):
    day: str             # "Mon", "Tue", ..., "Sun"
    day_index: int       # 0=Mon, 6=Sun
    avg_nightly: float | None = None
    sample_count: int = 0


class HrvInsight(_DefaultsRequired):
    level: str
    title: str
    detail: str


class HrvInsightsResponse(_DefaultsRequired):
    date: str
    day_stats: DailyHrvStats
    recovery: HrvRecovery
    quality: HrvDataQuality
    intraday_segments: list[HrvIntradaySegment] = []
    trend_band: HrvTrendBand
    streak: HrvStreak | None = None
    long_baseline: HrvLongBaseline | None = None
    baseline_bands: HrvBaselineBands | None = None
    distribution: HrvDistribution | None = None
    trajectory: HrvTrajectory | None = None
    status_mix: list[HrvStatusBucket] = []
    day_of_week: list[HrvDayOfWeekBucket] = []
    insights: list[HrvInsight] = []


class DailySleepStats(_DefaultsRequired):
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None


class DailySkinTempStats(_DefaultsRequired):
    deviation: float | None = None
    deviation_7_day: float | None = None
    nightly_value: float | None = None


class DailyMetric(_DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    heart_rate: DailyHeartRateStats
    stress: DailyMetricStats
    body_battery: DailyBodyBatteryStats
    spo2: DailyMetricStats
    respiration: DailyMetricStats
    hrv: DailyHrvStats
    sleep: DailySleepStats
    skin_temp: DailySkinTempStats


class PeriodHeartRateStats(_DefaultsRequired):
    avg: float | None = None
    avg_resting: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None
    zones: list[HRZoneBucket] = []


class PeriodMetricStats(_DefaultsRequired):
    avg: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None


class PeriodHrvStats(_DefaultsRequired):
    avg_nightly: float | None = None
    avg_weekly: float | None = None
    balanced_pct: float | None = None
    total_days: int = 0


class PeriodSpo2Stats(_DefaultsRequired):
    avg: float | None = None
    lowest_min: float | None = None
    low_days: int = 0
    total_days: int = 0


class PeriodSkinTempStats(_DefaultsRequired):
    avg_deviation: float | None = None
    max_deviation: float | None = None
    min_deviation: float | None = None
    avg_nightly: float | None = None
    days_tracked: int = 0


class PeriodSleepStats(_DefaultsRequired):
    avg_score: float | None = None
    avg_deep_score: float | None = None
    days_tracked: int = 0


class PeriodBodyBatteryStats(_DefaultsRequired):
    avg_min: float | None = None
    avg_max: float | None = None
    days_tracked: int = 0


class PeriodSummary(_DefaultsRequired):
    heart_rate: PeriodHeartRateStats
    stress: PeriodMetricStats
    respiration: PeriodMetricStats
    hrv: PeriodHrvStats
    spo2: PeriodSpo2Stats
    skin_temp: PeriodSkinTempStats
    sleep: PeriodSleepStats
    body_battery: PeriodBodyBatteryStats


class DailyAggregatesResponse(_DefaultsRequired):
    days: list[str]
    daily: list[DailyMetric]
    period_windows: dict[str, PeriodSummary] = {}


# ---------------------------------------------------------------------------
# Health assistant foundation models
# ---------------------------------------------------------------------------


DEFAULT_PROFILE_ID = "default"


class Goal(_DefaultsRequired):
    id: str
    title: str
    description: str | None = None
    status: str = "active"
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
    status: str = "active"
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
    completion_state: str = "completed"
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


class Experiment(_DefaultsRequired):
    id: str
    name: str
    status: str = "draft"
    start_date: str | None = None
    end_date: str | None = None
    goal: str | None = None
    hypothesis: str | None = None
    linked_routine_ids: list[str] = []
    outcome_metrics: list[str] = []
    expected_lag_days: list[int] = []
    confounder_notes: str | None = None
    priority: int = 0


class ExperimentExposure(_DefaultsRequired):
    id: str
    experiment_id: str
    date: str
    exposure_score: float | None = None
    adherence_state: str = "unknown"
    linked_routine_entry_ids: list[str] = []
    notes: str | None = None


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
    confidence: str = "insufficient"
    confounders: list[str] = []
    effects: list[ExperimentMetricEffect] = []


class Plan(_DefaultsRequired):
    id: str
    title: str
    scope: str
    status: str = "draft"
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
    completion_state: str = "pending"
    completion_notes: str | None = None


class AssistantThread(_DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"
    claude_session_id: str | None = None
    last_context_snapshot_id: str | None = None
    status: str = "active"
    last_message_at: str | None = None
    created_at: str | None = None


class AssistantMessage(_DefaultsRequired):
    id: str
    thread_id: str
    role: str
    content_markdown: str
    structured_payload_json: dict[str, object] = {}
    evidence_refs_json: list[str] = []
    created_at: str | None = None


class AssistantRun(_DefaultsRequired):
    id: str
    task_type: str
    status: str
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
    confidence: str = "insufficient"
    caveats: list[str] = []
    payload_json: dict[str, object] = {}


class TargetMetricDefinition(_DefaultsRequired):
    key: str
    label: str
    path: str
    unit: str


class GoalsResponse(_DefaultsRequired):
    goals: list[Goal] = []
    total: int


class RoutinesResponse(_DefaultsRequired):
    routines: list[Routine] = []
    total: int


class RoutineEntriesResponse(_DefaultsRequired):
    entries: list[RoutineEntry] = []
    total: int


class DailyCheckInsResponse(_DefaultsRequired):
    checkins: list[DailyCheckIn] = []
    total: int


class NotesResponse(_DefaultsRequired):
    notes: list[Note] = []
    total: int


class ExperimentsResponse(_DefaultsRequired):
    experiments: list[Experiment] = []
    total: int


class TargetMetricsResponse(_DefaultsRequired):
    metrics: list[TargetMetricDefinition] = []
    total: int


RendererFamily = Literal["timer_session", "checklist_block", "exercise_block"]
RoutineCadence = Literal["weekly", "biweekly"]
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
    cycle_week: int = 1
    weekday: WeekdayName
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSpec(_StrictDefaultsRequired):
    id: str
    name: str
    cadence: RoutineCadence
    start_date: str
    end_date: str | None = None
    status: str = "active"
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


class AssistantArtifactsResponse(_DefaultsRequired):
    artifacts: list[AssistantArtifact] = []
    total: int


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
    status: str = "active"
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    source_artifact_id: str | None = None


class CardTemplatesResponse(_DefaultsRequired):
    cards: list[CardTemplate] = []
    total: int


class RoutineSchedule(_DefaultsRequired):
    id: str
    name: str
    status: str = "active"
    cadence: RoutineCadence
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None


class RoutineAssignment(_DefaultsRequired):
    id: str
    routine_id: str
    card_template_id: str
    cycle_week: int = 1
    weekday: WeekdayName
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSchedulesResponse(_DefaultsRequired):
    routines: list[RoutineSchedule] = []
    total: int


class RoutineAssignmentsResponse(_DefaultsRequired):
    assignments: list[RoutineAssignment] = []
    total: int


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


class AssistantThreadsResponse(_DefaultsRequired):
    threads: list[AssistantThread] = []
    total: int


class AssistantMessagesResponse(_DefaultsRequired):
    messages: list[AssistantMessage] = []
    total: int


# ---------------------------------------------------------------------------
# Heart Rate Analysis models
# ---------------------------------------------------------------------------


class CircadianHRPoint(_DefaultsRequired):
    hour: int
    avg_bpm: float | None = None
    sample_count: int = 0


class SleepingHRPoint(_DefaultsRequired):
    date: str
    avg_sleeping_bpm: float | None = None
    ma7_bpm: float | None = None
    sample_count: int = 0


class RestingHRTrendPoint(_DefaultsRequired):
    date: str
    resting_bpm: int | None = None
    ma7_bpm: float | None = None


class DailyAvgHRTrendPoint(_DefaultsRequired):
    date: str
    avg_bpm: float | None = None
    ma7_bpm: float | None = None


class HRHistogramBin(_DefaultsRequired):
    bin_start: int
    bin_end: int
    count: int


class HRDistributionResponse(_DefaultsRequired):
    date: str
    bins: list[HRHistogramBin] = []
    sample_count: int = 0


class WeeklyRestingHRBox(_DefaultsRequired):
    iso_week: str
    min_bpm: float | None = None
    q1_bpm: float | None = None
    median_bpm: float | None = None
    q3_bpm: float | None = None
    max_bpm: float | None = None
    day_count: int = 0


class HRPatternWindow(_DefaultsRequired):
    """Pre-computed circadian profile for a time window."""
    circadian_profile: list[CircadianHRPoint] = []


class HeartRateAnalysisResponse(_DefaultsRequired):
    sleeping_hr_trend: list[SleepingHRPoint] = []
    resting_hr_trend: list[RestingHRTrendPoint] = []
    daily_avg_trend: list[DailyAvgHRTrendPoint] = []
    weekly_boxplots: list[WeeklyRestingHRBox] = []
    pattern_windows: dict[str, HRPatternWindow] = {}


class NightlyHrvTrendPoint(_DefaultsRequired):
    date: str
    nightly_avg: float | None = None
    ma7: float | None = None


class WeeklyHrvBox(_DefaultsRequired):
    iso_week: str
    min_ms: float | None = None
    q1_ms: float | None = None
    median_ms: float | None = None
    q3_ms: float | None = None
    max_ms: float | None = None
    day_count: int = 0


class HrvPatternWindow(_DefaultsRequired):
    """Pre-computed distribution + day-of-week for a time window."""
    distribution: HrvDistribution | None = None
    day_of_week: list[HrvDayOfWeekBucket] = []


class HrvAnalysisResponse(_DefaultsRequired):
    nightly_trend: list[NightlyHrvTrendPoint] = []
    weekly_boxplots: list[WeeklyHrvBox] = []
    pattern_windows: dict[str, HrvPatternWindow] = {}  # "3M", "6M", "All"


# ---------------------------------------------------------------------------
# Sleep analysis models
# ---------------------------------------------------------------------------


class SleepTrendPoint(_DefaultsRequired):
    date: str
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None
    ma7: float | None = None  # 7d MA of score


class WeeklySleepBox(_DefaultsRequired):
    iso_week: str
    min_score: float | None = None
    q1_score: float | None = None
    median_score: float | None = None
    q3_score: float | None = None
    max_score: float | None = None
    day_count: int = 0


class SleepAnalysisResponse(_DefaultsRequired):
    score_trend: list[SleepTrendPoint] = []
    weekly_boxplots: list[WeeklySleepBox] = []


# ---------------------------------------------------------------------------
# Stress analysis models
# ---------------------------------------------------------------------------


class StressTrendPoint(_DefaultsRequired):
    date: str
    avg: float | None = None
    ma7: float | None = None


class WeeklyStressBox(_DefaultsRequired):
    iso_week: str
    min_avg: float | None = None
    q1_avg: float | None = None
    median_avg: float | None = None
    q3_avg: float | None = None
    max_avg: float | None = None
    day_count: int = 0


class StressAnalysisResponse(_DefaultsRequired):
    avg_trend: list[StressTrendPoint] = []
    weekly_boxplots: list[WeeklyStressBox] = []


# ---------------------------------------------------------------------------
# Body Battery analysis models
# ---------------------------------------------------------------------------


class BodyBatteryTrendPoint(_DefaultsRequired):
    date: str
    min_val: int | None = None
    max_val: int | None = None
    ma7_min: float | None = None  # 7d MA of daily min


class WeeklyBodyBatteryBox(_DefaultsRequired):
    iso_week: str
    min_val: float | None = None
    q1_val: float | None = None
    median_val: float | None = None
    q3_val: float | None = None
    max_val: float | None = None
    day_count: int = 0


class BodyBatteryAnalysisResponse(_DefaultsRequired):
    trend: list[BodyBatteryTrendPoint] = []
    weekly_boxplots: list[WeeklyBodyBatteryBox] = []


class DaySummaryResponse(_DefaultsRequired):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(_DefaultsRequired):
    days: list[str]
    total: int


class IngestResult(_DefaultsRequired):
    days_ingested: int
    duration_ms: int


class IngestStatus(_DefaultsRequired):
    needs_ingest: bool
    last_ingest_time: str | None = None
    days_in_db: int
    days_on_disk: int


# ---------------------------------------------------------------------------
# Dashboard overview models
# ---------------------------------------------------------------------------


class ReadinessScore(_DefaultsRequired):
    score: int | None = None
    components: dict[str, float] = {}
    label: str | None = None  # "Ready", "Moderate", "Rest"


class CorrelationPoint(_DefaultsRequired):
    date: str
    hrv_nightly: float
    other_value: float


class MetricCorrelation(_DefaultsRequired):
    metric: str              # "sleep_score", "resting_hr"
    label: str               # "Sleep Score", "Resting HR"
    points: list[CorrelationPoint] = []
    r_value: float | None = None
    sample_count: int = 0


class TodayVitals(_DefaultsRequired):
    resting_hr: int | None = None
    resting_hr_delta_7d: float | None = None
    nightly_hrv: float | None = None
    nightly_hrv_delta_7d: float | None = None
    hrv_status: str | None = None
    sleep_score: int | None = None
    stress_avg: float | None = None


class SparklinePoint(_DefaultsRequired):
    date: str
    value: float | None = None
    ma7: float | None = None


class SparklineSummary(_DefaultsRequired):
    avg: float | None = None
    min: float | None = None
    max: float | None = None


class SparklineSeries(_DefaultsRequired):
    points: list[SparklinePoint] = []
    summary: SparklineSummary = SparklineSummary()


class DashboardSparklines(_DefaultsRequired):
    resting_hr: SparklineSeries = SparklineSeries()
    nightly_hrv: SparklineSeries = SparklineSeries()
    sleep_score: SparklineSeries = SparklineSeries()
    stress_avg: SparklineSeries = SparklineSeries()


class DashboardOverviewResponse(_DefaultsRequired):
    date: str
    readiness: ReadinessScore | None = None
    vitals: TodayVitals | None = None
    sparklines: DashboardSparklines | None = None
    correlations: list[MetricCorrelation] = []


# ---------------------------------------------------------------------------
# Program spec models
# ---------------------------------------------------------------------------


class Program(_DefaultsRequired):
    id: str
    name: str
    version: int
    status: str = "active"
    spec: dict[str, object] = {}
    imported_at: str | None = None
    updated_at: str | None = None
    retired_at: str | None = None


class ProgramVersion(_DefaultsRequired):
    program_id: str
    version: int
    spec: dict[str, object] = {}
    imported_at: str | None = None


class ProgramsResponse(_DefaultsRequired):
    programs: list[Program] = []
    total: int


class ProgramVersionsResponse(_DefaultsRequired):
    versions: list[ProgramVersion] = []
    total: int
