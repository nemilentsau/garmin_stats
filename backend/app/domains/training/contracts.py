"""Training-domain wire, persistence, and read-model contracts.

The strict v3 models parse the six-artifact import set documented in
``docs/training/artifact-schema-v3.md``. Uploaded block, bundle, registry,
and exercise-library JSON is stored verbatim; these models validate the wire
shape but never translate or re-author it. Authored programs live under
``docs/training/programs/``; calibration artifacts used only by tests live
under ``backend/tests/fixtures/training/``.

``Variant.prescription_patch`` and ``ExtensionRule.action`` remain opaque
dictionaries because they are structural partials whose valid shape depends
on the target prescription/event. Cross-object and compiled-schedule policy
belongs to ``application/validation.py``.

Models through ``ExerciseLibrary`` describe authored upload content.
``LintReport`` and ``Stored*`` describe activation output and persistence;
``TrainingCardLog`` describes per-occurrence capture; the ``Training*``
response models are read-only projections assembled by the application layer.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.contracts.base import DefaultsRequired, StrictDefaultsRequired

SchemaVersion3 = Literal["3.0"]
SlotName3 = Literal["morning", "midday", "evening"]
ContractKind = Literal["overload", "maintenance", "measurement", "recovery"]
Adaptation = Literal[
    "neural_force",
    "tendon_stiffness",
    "reactive_ability",
    "threshold",
    "vo2",
    "aerobic_base",
    "hypertrophy",
]
ProgressionDriver = Literal["load", "reps", "contacts", "pace", "duration", "density"]


class Cmp(StrictDefaultsRequired):
    """Leaf predicate: compares a named signal against a literal value."""

    signal: str
    op: Literal["<", "<=", ">", ">=", "==", "in"]
    value: bool | int | float | str | list[bool | int | float | str]


class AllPredicate(StrictDefaultsRequired):
    all: list[Predicate]


class AnyPredicate(StrictDefaultsRequired):
    any: list[Predicate]


class NotPredicate(StrictDefaultsRequired):
    """Negation predicate that accepts and emits the 'not' key.

    Serializes with `not_` by default; use `by_alias=True` to emit 'not'.
    Both spellings validate due to `populate_by_name=True`.
    """

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
        populate_by_name=True,
    )

    not_: Predicate = Field(alias="not")


Predicate = Cmp | AllPredicate | AnyPredicate | NotPredicate

AllPredicate.model_rebuild()
AnyPredicate.model_rebuild()
NotPredicate.model_rebuild()


class DoseSpec(StrictDefaultsRequired):
    sets: int | None = None
    reps: tuple[int, int] | None = None
    pct_e1rm: float | None = None
    rpe_max: float | None = None
    contacts: int | None = None
    duration_min: float | None = None
    distance_mi: float | None = None


class IntensityFloor(StrictDefaultsRequired):
    metric: Literal["pct_e1rm", "rpe", "zone"]
    min: float | str


class RampSpec(StrictDefaultsRequired):
    weeks: int
    endpoint: DoseSpec


class OverloadContract(StrictDefaultsRequired):
    kind: Literal["overload"]
    adaptation: Adaptation
    progression_driver: ProgressionDriver
    state_ref: str
    ramp: RampSpec | None = None


class MaintenanceContract(StrictDefaultsRequired):
    kind: Literal["maintenance"]
    preserves: str
    minimum_effective_dose: DoseSpec
    intensity_floor: IntensityFloor


class MeasurementContract(StrictDefaultsRequired):
    kind: Literal["measurement"]
    estimand: str
    quality_gate: list[Predicate]
    on_fail: Literal["retry_backup", "flag_and_continue", "extend_block"]


class RecoveryContract(StrictDefaultsRequired):
    kind: Literal["recovery"]
    load_ceiling: DoseSpec


Contract = Annotated[
    OverloadContract | MaintenanceContract | MeasurementContract | RecoveryContract,
    Field(discriminator="kind"),
]


class SegmentIntensity(StrictDefaultsRequired):
    zone: str | None = None
    rpe: float | None = None
    hr_range: tuple[int, int] | None = None


class SegmentSpec(StrictDefaultsRequired):
    label: str
    intensity: SegmentIntensity
    duration_min: float | None = None
    distance_mi: float | None = None


class SegmentPrescription(StrictDefaultsRequired):
    segments: list[SegmentSpec]


class LoadSpec(StrictDefaultsRequired):
    pct_e1rm: float | None = None
    rpe: float | None = None
    absolute_kg: float | None = None


class ExercisePrescriptionSpec(StrictDefaultsRequired):
    exercise_id: str
    targets: list[str]
    involves: list[str] = []
    sets: int
    reps: tuple[int, int]
    load: LoadSpec
    tempo: str | None = None
    logging: Literal["set_rep_load"]


class StrengthPrescription(StrictDefaultsRequired):
    exercises: list[ExercisePrescriptionSpec]


Prescription = StrengthPrescription | SegmentPrescription


class AnalysisContract(StrictDefaultsRequired):
    model_id: str
    decision_informed: str


class CaptureField(StrictDefaultsRequired):
    id: str
    type: Literal["number", "enum", "bool", "set_rep_load[]"]
    scale: dict[str, float] | None = None
    contract: AnalysisContract


class V3Card(StrictDefaultsRequired):
    id: str
    bundle_id: str
    name: str
    contract: Contract
    prescription: Prescription
    capture: list[CaptureField] = []
    display_notes: str | None = None
    est_duration_min: float | None = None


class Variant(StrictDefaultsRequired):
    id: str
    stimulus_fraction: float
    # Partial<Prescription>; merged by index at read time.
    prescription_patch: dict[str, Any] | None = None


class GuardedClause(StrictDefaultsRequired):
    when: Predicate
    select: str


class SelectionRule(StrictDefaultsRequired):
    clauses: list[GuardedClause]
    default: str
    on_missing_signal: Literal["select_conservative", "select_default", "ask"]


class V3Assignment(StrictDefaultsRequired):
    day: int
    slot: SlotName3
    card_id: str
    key_session: bool = False
    variants: list[Variant]
    selection: SelectionRule


class BudgetDeclaration(StrictDefaultsRequired):
    scope: Literal["week"]
    minutes_max: float
    minutes_min: float | None = None


class V3Bundle(StrictDefaultsRequired):
    id: str
    name: str
    schema_version: SchemaVersion3
    owns: list[str] = []
    cards: list[V3Card]
    assignments: list[V3Assignment]
    declared_budgets: list[BudgetDeclaration] = []


class BlockWindow(StrictDefaultsRequired):
    start: str
    days: int


class StepResponse(StrictDefaultsRequired):
    week: int
    variable: str
    target_fraction: float
    held_constant: list[str] = []


class MeasurementEvent(StrictDefaultsRequired):
    id: str
    card_id: str
    estimand: str
    scheduled_day: int
    backup_days: list[int] = []
    required: bool
    on_all_missed: Literal["extend_block", "flag"]


class ConstraintReference(StrictDefaultsRequired):
    card_id: str | None = None
    key_session: bool | None = None
    per_tissue_duplicate: bool | None = None


class ForbidSpec(StrictDefaultsRequired):
    contract_kind: list[ContractKind] | None = None
    targets: list[str] | None = None


class SchedulingConstraint(StrictDefaultsRequired):
    id: str
    forbid: ForbidSpec
    relation: Literal["within_hours_before", "within_hours_after", "same_day_as"]
    hours: float | None = None
    reference: ConstraintReference


class Criterion(StrictDefaultsRequired):
    id: str
    predicate: Predicate


class ExtensionRule(StrictDefaultsRequired):
    when_failed: str
    action: dict[str, Any]
    cap_total_extension_days: int


class ReviewComputed(StrictDefaultsRequired):
    id: str
    estimator_id: str


class ReviewSpec(StrictDefaultsRequired):
    cadence: Literal["weekly", "block_end"]
    computed: list[ReviewComputed] = []
    human_prompts: list[str] = []


class V3Block(StrictDefaultsRequired):
    id: str
    name: str | None = None
    identity: Literal["measurement", "development", "consolidation", "taper", "race"]
    window: BlockWindow
    bundle_ids: list[str]
    baseline_tags: list[str] = []
    flat_weeks: list[int] = []
    step_response: StepResponse | None = None
    measurement_events: list[MeasurementEvent] = []
    scheduling_constraints: list[SchedulingConstraint] = []
    exit_criteria: list[Criterion] = []
    extension_rules: list[ExtensionRule] = []
    review_specs: list[ReviewSpec] = []


class SignalDef(StrictDefaultsRequired):
    id: str
    units: str
    source: Literal["garmin", "derived", "manual"]
    staleness_hours: float


class EstimatorPrior(StrictDefaultsRequired):
    value: float
    sigma: float
    source: str


class EstimatorDef(StrictDefaultsRequired):
    id: str
    inputs: list[str]
    output_signal: str
    prior: EstimatorPrior | None = None


class SwcSpec(StrictDefaultsRequired):
    method: Literal["rolling_sd"]
    window_days: int
    k: float


class StateComponent(StrictDefaultsRequired):
    id: str
    description: str
    signal: str
    estimator_id: str
    swc: SwcSpec


class ProgressTerm(StrictDefaultsRequired):
    state: str
    weight: float


class ConstraintBand(StrictDefaultsRequired):
    lo: float | None = None
    hi: float | None = None


class ConstraintViolationAction(StrictDefaultsRequired):
    action: Literal["select_conservative_variants", "insert_recovery_day", "flag_review"]
    scope: Literal["next_day", "next_3_days"]


class ConstraintSpec(StrictDefaultsRequired):
    signal: str
    band: ConstraintBand
    on_violation: ConstraintViolationAction


class ObjectiveSpec(StrictDefaultsRequired):
    progress: list[ProgressTerm]
    constraints: list[ConstraintSpec]


class SignalRegistry(StrictDefaultsRequired):
    schema_version: SchemaVersion3
    signals: list[SignalDef]
    estimators: list[EstimatorDef]
    state_vector: list[StateComponent]
    objective: ObjectiveSpec


class ExerciseDef(StrictDefaultsRequired):
    id: str
    name: str
    targets: list[str] = []
    involves: list[str] = []


class ExerciseLibrary(StrictDefaultsRequired):
    schema_version: SchemaVersion3
    exercises: list[ExerciseDef]


class LintReport(DefaultsRequired):
    """L1-L12 findings plus the weekly rollups the block's budgets are checked against."""

    errors: list[str] = []
    warnings: list[str] = []
    week_run_miles: dict[int, float] = {}
    week_minutes_by_bundle: dict[int, dict[str, float]] = {}


StoredRecordStatus = Literal["active", "retired"]
"""Lifecycle status for a stored block/bundle row (`application/imports.py`
retires the previous generation before activating a new one)."""


class StoredBundle(DefaultsRequired):
    """One imported content bundle, keyed by its own artifact id.

    `artifact` is the uploaded bundle JSON stored verbatim — never a
    re-serialized round trip through `V3Bundle` — so a readback always equals
    exactly what was uploaded.
    """

    id: str
    status: StoredRecordStatus
    artifact: dict[str, Any]


class StoredBlock(DefaultsRequired):
    """The active (or a formerly active, now retired) imported block.

    Carries the lint report and warning acknowledgements produced at
    activation time alongside the verbatim block artifact, so a later reader
    never has to re-lint to know why a block was allowed to activate.
    """

    id: str
    status: StoredRecordStatus
    artifact: dict[str, Any]
    lint_report: LintReport
    warning_acks: list[str] = []
    activated_at: str
    schedule_start: str | None = None
    # None is accepted only while loading a pre-instance-identity database;
    # schema startup backfills it before normal application reads.
    program_instance_id: str | None = None


class StoredRegistry(DefaultsRequired):
    """The single imported signal registry, replaced wholesale on every import.

    The raw registry artifact has no id of its own; `id` is an
    import-assigned bookkeeping value, not part of the artifact.
    """

    id: str
    artifact: dict[str, Any]


class StoredLibrary(DefaultsRequired):
    """The single imported exercise library, replaced wholesale on every import."""

    id: str
    artifact: dict[str, Any]


class TrainingSetLog(StrictDefaultsRequired):
    """One logged set within a strength card's capture."""

    set_index: Annotated[int, Field(ge=0)]
    weight: Annotated[float, Field(ge=0)] | None = None
    reps: Annotated[int, Field(ge=0)] | None = None
    rir: Annotated[int, Field(ge=0, le=10)] | None = None


class TrainingExerciseLog(StrictDefaultsRequired):
    """Logged sets for one exercise within a card's capture."""

    exercise_id: str
    sets: list[TrainingSetLog] = []


class TrainingCheckinLog(StrictDefaultsRequired):
    """Logged tissue soreness/flags/core-done for a check-in card."""

    soreness: dict[str, Annotated[int, Field(ge=0, le=3)]] = {}
    flags: dict[str, bool] = {}
    core_done: bool | None = None


class TrainingCaptureLog(StrictDefaultsRequired):
    """Everything a card's capture fields recorded for one occurrence."""

    set_logs: list[TrainingExerciseLog] = []
    checkin: TrainingCheckinLog | None = None
    rpe: Annotated[float, Field(ge=1, le=10)] | None = None


TrainingCardStatus = Literal["pending", "completed", "partial", "skipped"]


class TrainingExecutionEvaluation(DefaultsRequired):
    """Effective completion state after considering logs and tracked runs.

    `run_id` identifies tracked-run evidence only, so it is populated only
    when `source` is `tracked_run`; associations remain available separately
    on `TrainingTodayCard.associated_activity`.
    """

    status: TrainingCardStatus
    source: Literal["manual_log", "tracked_run", "none"]
    run_id: str | None = None


class TrainingCardLog(DefaultsRequired):
    """One card occurrence's completion state, owned by a program instance."""

    id: str  # f"{program_instance_id}:{date}:{occurrence_key}" for current rows
    date: str
    # Opaque display key; ordinary/base form is bundle:card:dNN, while every
    # activated backup adds an event-qualified suffix for stable ownership.
    occurrence_key: str
    # None is a legacy-row compatibility state consumed only by schema migration.
    program_instance_id: str | None = None
    status: TrainingCardStatus = "pending"
    variant_taken: str | None = None
    notes: str | None = None
    capture: TrainingCaptureLog | None = None
    linked_run_id: str | None = None  # manual run-card link; wins over auto-matching
    run_link_detached: bool = False  # explicitly cleared auto-match; no linked_run_id set


class TrainingLastLogged(DefaultsRequired):
    """Most recent logged set for an exercise — the load anchor.

    Built by `application/read_models.py`'s `last_logged_for` from prior
    `TrainingCardLog` history; only ever populated on the Today path (the
    schedule-window planning view always renders `last=None`).
    """

    weight_kg: float | None = None
    reps: int | None = None
    date: str


class TrainingExerciseDisplay(DefaultsRequired):
    """One strength exercise's read-only display projection for a scheduled card."""

    exercise_id: str
    name: str  # from the exercise library
    scheme: str  # "3×2–3 @ 87% e1RM"
    tempo: str | None = None
    sets: int
    log_sets: bool  # True when the card's capture includes a set_rep_load[] field
    reps_low: int
    reps_high: int
    load_kind: Literal["pct_e1rm", "rpe", "absolute_kg"] | None = None
    load_value: float | None = None
    last: TrainingLastLogged | None = None


class TrainingSegmentDisplay(DefaultsRequired):
    """One run/support segment's read-only display projection for a scheduled card."""

    label: str
    detail: str  # "7 mi · 55 min · Z1-Z2"
    distance_mi: float | None = None
    duration_min: float | None = None
    zone: str | None = None  # None for rpe-only/hr_range-only segments (e.g. drills, strides)


class TrainingCheckinRow(DefaultsRequired):
    """One tissue soreness prompt row for the daily check-in card."""

    tissue: str
    label: str


class TrainingRunActivitySummary(DefaultsRequired):
    """Training-local projection of a tracked run; imperial display units.

    Built entirely outside `training` — the injected `RunActivityReadPort`
    (`dependencies.py`) is the only source of these — so this contract never
    round-trips through `garmin_analytics`/`garmin_health` vocabulary or
    units; the adapter that produces it (`bootstrap/run_activity_port.py`)
    does the m->mi / min-per-km->min-per-mi conversion once, at the
    composition boundary. `link_source` distinguishes a run picked by the
    read models' auto-matching policy (`"auto"`) from one a person manually
    linked via the capture-log PATCH (`"manual"`).
    """

    run_id: str
    session_date: str
    start_time_local: str
    distance_mi: float | None = None
    timer_time_s: float | None = None
    pace_min_per_mi: float | None = None
    avg_heart_rate_bpm: int | None = None
    hr_source: str | None = None
    training_load: float | None = None
    aerobic_training_effect: float | None = None
    link_source: Literal["auto", "manual"] = "auto"


class TrainingRunWalkSpan(DefaultsRequired):
    """Training-local run/walk/stand span, in seconds from session start."""

    span_type: str
    start_s: float
    end_s: float


class TrainingRunEvidence(DefaultsRequired):
    """Training-local session summary plus index-aligned analytical series."""

    summary: TrainingRunActivitySummary
    elapsed_s: list[int]
    distance_mi: list[float | None]
    heart_rate_bpm: list[int | None]
    run_walk_spans: list[TrainingRunWalkSpan]
    dew_point_c: float | None = None


MeasurementStatus = Literal["awaiting_review", "valid", "provisional", "failed"]
GateResult = Literal["pass", "fail", "unknown"]
MeasurementGateValue = bool | int | float | str


class TrainingRequiredAction(DefaultsRequired):
    """Authored block action exposed after a required event exhausts its attempts."""

    event_id: str
    action: Literal["extend_block", "flag"]


class TrainingMeasurementAssessment(DefaultsRequired):
    """Training-local projection of the coach's subjective measurement judgment."""

    status: Literal["valid", "provisional", "failed"]
    rationale: str
    source_id: str


class TrainingMeasurementObservations(DefaultsRequired):
    """Objective values extracted from a tracked measurement run."""

    final20_hr_bpm: int | None = None
    threshold_pace_min_per_mi: float | None = None
    strap_validity_pct: float | None = None
    effort_stand_time_s: float = 0.0


class TrainingMeasurementGate(DefaultsRequired):
    """One authored quality-gate comparison and its objective result."""

    signal: str
    value: MeasurementGateValue | None = None
    operator: Literal["<", "<=", ">", ">=", "==", "in"]
    threshold: MeasurementGateValue | list[MeasurementGateValue]
    result: GateResult


class TrainingMeasurementWarning(DefaultsRequired):
    """Objective protocol evidence that is not an authored hard gate."""

    code: str
    value: MeasurementGateValue | None = None
    message: str


class TrainingMeasurementEvaluation(DefaultsRequired):
    """Objective run evidence composed with the exact coach assessment."""

    status: MeasurementStatus
    run_id: str
    observations: TrainingMeasurementObservations
    gates: list[TrainingMeasurementGate] = Field(default_factory=list)
    warnings: list[TrainingMeasurementWarning] = Field(default_factory=list)
    rationale: str | None = None
    assessment_source_id: str | None = None
    estimator_eligible: bool = False
    retry_required: bool = False


class TrainingTodayCard(DefaultsRequired):
    """One scheduled card occurrence, fully projected for Today-board display."""

    program_instance_id: str
    occurrence_key: str
    occurrence_id: str
    date: str
    day: int
    slot: SlotName3
    bundle_id: str
    bundle_name: str
    is_running: bool
    card: V3Card  # verbatim
    key_session: bool = False
    variants: list[Variant] = []
    rule_display: str | None = None  # omitted when the selection rule has no clauses
    gate_display: str | None = None  # measurement cards only
    variant_options: list[str] = []  # omitted when the assignment has < 2 variants
    segments_display: list[TrainingSegmentDisplay] = []
    exercises_display: list[TrainingExerciseDisplay] = []
    checkin_rows: list[TrainingCheckinRow] = []  # non-empty only for the check-in card
    capture_rpe: bool = False  # card captures a numeric RPE
    est_duration_min: float | None = None
    status: TrainingCardStatus = "pending"
    execution: TrainingExecutionEvaluation
    variant_taken: str | None = None
    notes: str | None = None
    capture: TrainingCaptureLog | None = None
    associated_activity: TrainingRunActivitySummary | None = None  # run cards only
    run_candidates: list[TrainingRunActivitySummary] = []  # run cards only
    measurement: TrainingMeasurementEvaluation | None = None  # measurement runs only
    measurement_event_id: str | None = None
    measurement_attempt: Literal["scheduled", "backup"] | None = None

    @model_validator(mode="after")
    def _execution_matches_legacy_status(self) -> TrainingTodayCard:
        if self.execution.status != self.status:
            raise ValueError("execution status must match legacy status")
        return self


class TrainingTodayResponse(DefaultsRequired):
    """One day's compiled schedule, enriched with any saved capture logs."""

    date: str
    program_instance_id: str | None = None
    block_id: str | None = None
    block_name: str | None = None
    block_days: int | None = None
    schedule_start: str | None = None
    day: int | None = None  # None when date is outside the active window
    cards: list[TrainingTodayCard] = []


class TrainingScheduleDay(DefaultsRequired):
    """One calendar day within a multi-day schedule window projection."""

    date: str
    day: int
    cards: list[TrainingTodayCard] = []


class TrainingScheduleWindow(DefaultsRequired):
    """A multi-day schedule projection (e.g. a two-week planning view)."""

    start_date: str
    end_date: str
    days: list[TrainingScheduleDay] = []
    required_actions: list[TrainingRequiredAction] = []


class TrainingBlockStatus(DefaultsRequired):
    """The active block's lifecycle snapshot: lint history plus burn-in phase."""

    block: V3Block
    block_name: str
    schedule_start: str
    lint_report: LintReport
    warning_acks: list[str] = []
    current_day: int | None = None
    burn_in: bool | None = None  # True during week 1
    activated_at: str
