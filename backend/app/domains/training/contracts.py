"""V3 wire contracts for the training domain.

Owns the strict Pydantic models that parse the v3 artifacts under
`docs/routine-pivot/block0/` — three content bundles (`running_v3.json`,
`strength_v3.json`, `support_v3.json`), the block definition (`block0.json`),
the signal registry (`registry.json`), and the exercise library
(`exercise_library.json`). These models mirror `docs/routine-pivot/
schema_v3_spec.md` §1-§8, but the shipped artifacts are the actual contract:
where a field in an artifact would fail to parse against the markdown spec,
the model here is adjusted to fit the artifact, never the other way around.
The artifacts are read-only canon and are never reformatted.

Fields present in the artifacts but absent from `schema_v3_spec.md` (kept
here rather than in the spec doc, since the spec is descriptive and the
artifacts are authoritative):

- `V3Card.est_duration_min: float | None` — every card in all three bundles
  carries this field; the markdown spec's `Card` interface doesn't declare
  it.

Two fields the spec *does* declare are deliberately typed looser than a
literal reading, because Pydantic can't express the spec's shape and the
artifacts don't need it to:

- `Variant.prescription_patch: dict[str, Any] | None` — the spec types this
  `Partial<Prescription>` (TS structural partial, no Pydantic equivalent).
  Bundle authors only ever populate a subset of `SegmentSpec` keys inside it
  (e.g. `label`/`intensity` without `duration_min`), so it stays an
  unvalidated opaque dict, merged by index at read time by a later task.
- `ExtensionRule.action: dict[str, Any]` — the spec types this
  `{ extend_days: number; insert?: MeasurementEvent }`; `block0.json` only
  ever uses `{"extend_days": <int>}`. Left as an opaque dict rather than a
  closed shape since no artifact exercises `insert`.

Every model here parsed the six shipped artifacts on the first pass with no
adjustments beyond what's listed above — no field in any artifact failed to
parse against this contract set.

This module intentionally does not parse `compiled_schedule.json`,
`lint_report.json`, or `schedule_overview.md` — those are derived/reporting
artifacts, not part of the v3 wire contract surface.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.base import StrictDefaultsRequired

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
    est_duration_min: float | None = None  # artifact field, not in the markdown spec


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
    identity: Literal["measurement", "development", "consolidation", "taper", "race"]
    window: BlockWindow
    bundle_ids: list[str]
    baseline_tags: list[str] = []
    flat_weeks: list[int] = []  # artifact field
    step_response: StepResponse | None = None  # artifact field
    measurement_events: list[MeasurementEvent] = []
    scheduling_constraints: list[SchedulingConstraint] = []  # artifact field
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
