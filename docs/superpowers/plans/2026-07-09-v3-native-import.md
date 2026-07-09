# V3-Native Import & Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The six `docs/routine-pivot/block0/` artifacts upload through a Training → Import page, validate via the ported linter, activate, and execute on the Today board with working capture — v3 stored verbatim, no translation anywhere.

**Architecture:** New backend domain slice `backend/app/domains/training/` (contracts mirroring `schema_v3_spec.md` §1–§8 with artifact precedence, jsonstore storage of verbatim artifacts, ported L1–L12 validator, compile + read-model projections, capture logs) + new frontend surfaces (`/training/import` page; training section on Today/Schedule with v3-native card components under `frontend/src/lib/training/`). The old `routines` domain is untouched. Spec: `docs/superpowers/specs/2026-07-09-v3-native-import-design.md`.

**Tech Stack:** FastAPI + Pydantic (Python 3.14, `uv`), jsonstore/SQLite, SvelteKit 5 (runes), openapi-fetch generated types.

## Global Constraints

- Branch `refactor-routines`, main checkout. `uv` only.
- Python gates before every commit: `cd backend && uv run pytest tests/ -v && uv run ruff check && uv run pyright app/ tests/` — 0 errors. Frontend: `cd frontend && npm run check` — 0 errors. API schema changes → `bash scripts/generate-api-types.sh`, commit `api-types.ts`.
- **Import-only principle:** no code path may create routine/experiment/training content except the import endpoint. No seeds, no fixtures written to the real DB, no generators.
- **v3 artifacts are canon and READ-ONLY** (`docs/routine-pivot/block0/*.json`). Contracts must parse them AS-IS; where `schema_v3_spec.md` and the artifacts disagree, artifacts win. Tests use them as read-only fixtures via `REPO_ROOT` (pattern: `backend/tests/_architecture.py:7`, usage like the old `test_artifact_bundles.py` fixture loading).
- **The v2 `CardPayload`/`CardActual` unions and the `routines` domain must not be imported by the training domain** — the cross-slice allowlist test (`backend/tests/architecture/test_architecture_cross_slice_imports.py`) will fail on any cross-slice import; the training slice needs zero entries.
- Architecture patterns to satisfy (see `backend/tests/architecture/test_architecture_programs_boundaries.py` as the template): application/dependencies modules never mention `fastapi`/`build_container`; `adapters.py` uses `app.infra.jsonstore` and defines `SqliteTrainingRepository`; routes resolve the repo via `build_container().training_repo`; router mounted in `bootstrap/routing.py`.
- Frontend is display-only — all projections (display strings, rule English, tissue expansion) come from backend read models.
- Read `.claude/skills/testing/SKILL.md` before writing tests: one test per branch, two per boundary, explicit idempotence tests for import/activation.
- Contract bases: `DefaultsRequired` / `StrictDefaultsRequired` / `AutoTotalResponse` from `app/contracts/base.py`. Ruff line length 100, pyright standard.

**Block-day fact for verification tasks:** window start 2026-07-06; `date = window.start + (day - 1)`.

---

### Task 1: v3 contracts that parse the artifacts verbatim

**Files:**
- Create: `backend/app/domains/training/__init__.py` (docstring only), `backend/app/domains/training/contracts.py`
- Test: `backend/tests/domains/training/__init__.py`, `backend/tests/domains/training/test_contracts.py`

**Interfaces (produced — later tasks import these exact names):**
`V3Bundle`, `V3Card`, `Contract` (discriminated union on `kind`), `OverloadContract`, `MaintenanceContract`, `MeasurementContract`, `RecoveryContract`, `DoseSpec`, `IntensityFloor`, `RampSpec`, `Prescription = StrengthPrescription | SegmentPrescription`, `SegmentPrescription`, `SegmentSpec`, `SegmentIntensity`, `ExercisePrescriptionSpec`, `LoadSpec`, `CaptureField`, `AnalysisContract`, `V3Assignment`, `Variant`, `SelectionRule`, `GuardedClause`, `Predicate` (recursive: `Cmp | AllPredicate | AnyPredicate | NotPredicate`), `V3Block`, `BlockWindow`, `StepResponse`, `MeasurementEvent`, `SchedulingConstraint`, `Criterion`, `ExtensionRule`, `ReviewSpec`, `SignalRegistry`, `SignalDef`, `EstimatorDef`, `StateComponent`, `ObjectiveSpec`, `ConstraintSpec`, `ExerciseLibrary`, `ExerciseDef`.

- [ ] **Step 1: Failing test — the six artifacts parse and round-trip:**

```python
"""V3 contract fidelity: the shipped Block 0 artifacts are the parsing contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domains.training.contracts import (
    ExerciseLibrary,
    SignalRegistry,
    V3Block,
    V3Bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
BLOCK0 = REPO_ROOT / "docs" / "routine-pivot" / "block0"


def _load(name: str) -> dict:
    return json.loads((BLOCK0 / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["running_v3.json", "strength_v3.json", "support_v3.json"])
def test_shipped_bundles_parse_and_round_trip(name: str):
    raw = _load(name)
    bundle = V3Bundle.model_validate(raw)
    assert V3Bundle.model_validate(bundle.model_dump(exclude_none=True)) == bundle


def test_shipped_block_parses_including_artifact_only_fields():
    block = V3Block.model_validate(_load("block0.json"))
    assert block.flat_weeks == [1, 2, 3]
    assert block.step_response is not None and block.step_response.target_fraction == 0.67
    assert len(block.scheduling_constraints) == 3


def test_shipped_registry_and_library_parse():
    registry = SignalRegistry.model_validate(_load("registry.json"))
    assert len(registry.state_vector) == 5
    library = ExerciseLibrary.model_validate(_load("exercise_library.json"))
    assert any(e.id == "pendulum_squat" for e in library.exercises)


def test_unknown_keys_are_rejected():
    raw = _load("block0.json")
    raw["surprise"] = 1
    with pytest.raises(ValidationError):
        V3Block.model_validate(raw)


def test_contract_kind_discriminates():
    raw = _load("strength_v3.json")
    assert {c["contract"]["kind"] for c in raw["cards"]} == {"overload"}
    bundle = V3Bundle.model_validate(raw)
    assert all(card.contract.kind == "overload" for card in bundle.cards)
```

- [ ] **Step 2: Run to verify failure** — module missing.
- [ ] **Step 3: Implement `contracts.py`.** Module docstring: owns the v3 wire contracts, mirrors `schema_v3_spec.md` §1–§8, artifacts take precedence over the markdown spec. All models extend `StrictDefaultsRequired` EXCEPT where noted. Complete model set:

```python
SchemaVersion3 = Literal["3.0"]
SlotName3 = Literal["morning", "midday", "evening"]
ContractKind = Literal["overload", "maintenance", "measurement", "recovery"]
Adaptation = Literal[
    "neural_force", "tendon_stiffness", "reactive_ability",
    "threshold", "vo2", "aerobic_base", "hypertrophy",
]
ProgressionDriver = Literal["load", "reps", "contacts", "pace", "duration", "density"]


class Cmp(StrictDefaultsRequired):
    signal: str
    op: Literal["<", "<=", ">", ">=", "==", "in"]
    value: bool | int | float | str | list[bool | int | float | str]


class AllPredicate(StrictDefaultsRequired):
    all: list["Predicate"]


class AnyPredicate(StrictDefaultsRequired):
    any: list["Predicate"]


class NotPredicate(StrictDefaultsRequired):
    not_: "Predicate" = Field(alias="not")


Predicate = Cmp | AllPredicate | AnyPredicate | NotPredicate


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
    prescription_patch: dict[str, Any] | None = None  # Partial<Prescription>; merged by index at read time


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
    flat_weeks: list[int] = []                      # artifact field
    step_response: StepResponse | None = None       # artifact field
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
```

Notes for the implementer: recursive `Predicate` needs `model_rebuild()` calls after definition; `NotPredicate` uses `Field(alias="not")` with `populate_by_name` off (artifacts use `"not"`); if any artifact field fails to parse, adjust the CONTRACT (artifacts win) and record the delta in the module docstring. Verify `tuple[int, int]` coerces from JSON arrays (pydantic v2 does).

- [ ] **Step 4: Run tests + gates** → green. If parsing reveals additional artifact-only fields, add them and note in the report.
- [ ] **Step 5: Commit** — `feat(training): v3 wire contracts parsing Block 0 artifacts verbatim` (+ Co-Authored-By trailer).

---

### Task 2: compile + validator (linter port)

**Files:**
- Create: `backend/app/domains/training/application/__init__.py`, `backend/app/domains/training/application/compile.py`, `backend/app/domains/training/application/validation.py`
- Test: `backend/tests/domains/training/test_validation.py`

**Interfaces:**
- Consumes: Task 1 contracts.
- Produces:
  - `compile.py`: `CompiledEntry` (dataclass or `DefaultsRequired` model: `day: int`, `slot: SlotName3`, `bundle_id: str`, `card: V3Card`, `assignment: V3Assignment`), `compile_schedule(bundles: list[V3Bundle]) -> list[CompiledEntry]` (sorted by day, slot hour morning=7/midday=13/evening=19, matching linter), `apply_patch(prescription: dict, patch: dict | None) -> dict` (index-merge, verbatim port of linter `apply_full_patch` semantics), `entry_minutes(entry: CompiledEntry) -> float`, `week_of(day: int) -> int`.
  - `validation.py`: `LintReport` (`DefaultsRequired`: `errors: list[str]`, `warnings: list[str]`, `week_run_miles: dict[int, float]`, `week_minutes_by_bundle: dict[int, dict[str, float]]`), `lint(block: V3Block, bundles: list[V3Bundle], registry: SignalRegistry, library: ExerciseLibrary) -> LintReport`.

- [ ] **Step 1: Failing tests.** Core cases (full code per this shape; one test per rule branch — read `.claude/skills/testing/SKILL.md` first):

```python
def _block0_artifacts():
    # loads all six via REPO_ROOT, returns (block, bundles, registry, library)

def test_block0_artifacts_lint_clean_and_reproduce_shipped_report():
    block, bundles, registry, library = _block0_artifacts()
    report = lint(block, bundles, registry, library)
    assert report.errors == [] and report.warnings == []
    shipped = json.loads((BLOCK0 / "lint_report.json").read_text())
    assert report.week_run_miles == {int(k): v for k, v in shipped["week_run_miles"].items()}
```

plus one synthetic-violation test per rule, each mutating a deep copy of the parsed artifacts and asserting the rule id appears in `errors` (or `warnings` for L11): L1 (drop a contract field via raw dict → contract validation happens in Task 1, so L1's residual check = unknown `state_ref`), L2 (add `quad` to running bundle's `owns`), L3 (shrink strength `minutes_max` to 100), L4 (set a card `display_notes` to "skip if tired"), L5 (move an `sup.hsr_a` assignment onto day 11 morning → within 24h before day-12 test), L6 (add an unconsumed signal to the registry; strip `backup_days` from the required event), L7 (repoint S2's estimator to one with only ambient inputs → hardened transitive check fires), L8 (blank a run card's segments), L9 (change one flat-week easy-run distance by +2 mi), L10 (set an assignment's selection default to "reduced"; set a non-skip variant `stimulus_fraction` to 0.4; add a clause selecting "plus"), L11 (remove `protocol-change` from `baseline_tags` → warning), L12 (empty `exit_criteria`).

- [ ] **Step 2: Verify failure** (modules missing).
- [ ] **Step 3: Implement.** `compile.py` ports the linter's compile section (lines 29–89 of `docs/routine-pivot/block0/linter.py`) onto the typed contracts. `validation.py` ports L1–L12 **rule-for-rule from `linter.py` — the file is the source; port, don't reinvent**, with exactly three deltas: (a) L7 covered-check walks the estimator DAG transitively from the state component's estimator inputs until it reaches a `cap.*` field that a scheduled card captures (bounded by visited-set); (b) L11 computes week-1 novelty as the count of distinct overload `adaptation` kinds appearing in week 1 instead of the hardcoded `novel = 3`; (c) rule messages keep the linter's `[L#][ERROR]` prefix format so reports read identically. Everything else (L4 regex, L5 hour math, L6 closure sets, L9 3% flatness, L10 checks) stays semantically identical. Docstrings per house style (what the module owns, why the three deltas exist).
- [ ] **Step 4: Run tests + full gates** → green. The block0 parity test is the keystone: if it fails, the port is wrong (never "fix" it by editing artifacts).
- [ ] **Step 5: Commit** — `feat(training): schedule compiler + L1-L12 validator ported from block0 linter`.

---

### Task 3: storage + import application

**Files:**
- Create: `backend/app/domains/training/schema.py`, `backend/app/domains/training/adapters.py`, `backend/app/domains/training/dependencies.py`, `backend/app/domains/training/application/imports.py`
- Modify: `backend/app/bootstrap/schema.py` (call `init_training_schema`), `backend/app/bootstrap/container.py` (add `training_repo: SqliteTrainingRepository`)
- Test: `backend/tests/domains/training/test_imports.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - Tables (all `JSON_RECORD_COLUMNS_SQL` shape): `training_bundles`, `training_blocks`, `training_registry`, `training_exercise_library`, `training_card_logs`.
  - Stored wrapper records (`DefaultsRequired`, in `contracts.py`): `StoredBundle{id, status: Literal["active","retired"], artifact: dict}`, `StoredBlock{id, status, artifact: dict, lint_report: LintReport, warning_acks: list[str], activated_at: str}`, `StoredRegistry{id, artifact: dict}`, `StoredLibrary{id, artifact: dict}`. `artifact` is the uploaded JSON **verbatim** (store the raw dict, not a re-serialized model).
  - `dependencies.py`: `TrainingRepository(Protocol)` — `active_block() -> StoredBlock | None`, `bundles_for(block_id_or_ids) -> list[StoredBundle]`, `registry() -> StoredRegistry | None`, `library() -> StoredLibrary | None`, `save_import(block, bundles, registry, library) -> None` (single transaction; retires any previously active block/bundles), `card_log(date, occurrence_key)`, `card_logs_for(date) -> list[TrainingCardLog]`, `upsert_card_log(log) -> None`.
  - `imports.py`: `ImportFile` (`StrictDefaultsRequired`: `filename: str`, `content: dict`), `ImportRequest{files: list[ImportFile], warning_acks: list[str] = []}`, `ImportResult{files: list[FileValidation{filename, kind, valid, errors}], lint_report: LintReport | None, missing_kinds: list[str], activated: bool}`, `import_artifacts(repo, request) -> ImportResult`. Kind detection from content keys: `cards`→bundle, `identity`→block, `signals`→registry, `exercises`→library; unknown → invalid file. Single-shot semantics: everything validates AND the set is complete (1 block + all `bundle_ids` present + registry + library) AND lint has no errors AND every warning string appears in `warning_acks` → store verbatim + activate; otherwise store NOTHING and return the full diagnosis (`activated=False`).

- [ ] **Step 1: Failing tests** — behaviors (full code following the shape of `_block0_artifacts` + tmp_db autouse fixture; the conftest `tmp_db` gives a fresh DB per test once `init_training_schema` is wired):
  - full six-file import → `activated=True`; readback: `repo.active_block().artifact == uploaded block dict` (verbatim equality), same for one bundle; lint report persisted with the block.
  - re-import of the identical set → still exactly one active block, one registry row, three active bundles (idempotent replace, not duplicates).
  - incomplete set (drop the registry file) → `activated=False`, `missing_kinds == ["registry"]`, and NOTHING stored (`repo.active_block() is None`).
  - a lint error (mutated ownership clash) → `activated=False`, error listed, nothing stored.
  - a warning without ack → not activated; same import with the ack string → activated.
  - unknown file content → that file `valid=False`, set not activated.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** per the patterns: `schema.py` mirrors `programs/schema.py` (f-string DDL + `init_training_schema(con)`); register in `bootstrap/schema.py`; `adapters.py` `_STORE = JsonStore({...5 tables})`, `SqliteTrainingRepository` with `save_import` doing one `with connect() as con, con:` transaction using `save_in_connection` (retire-then-save; single active block invariant); container gains `training_repo`. `imports.py` is pure policy: detect kinds → validate contracts (collect per-file errors) → completeness → `compile_schedule` + `lint` → ack check → `repo.save_import(...)`. Raise nothing for user errors — diagnosis rides the result (routes return it as 200 with `activated=False`; contract-invalid files are per-file errors, not exceptions).
- [ ] **Step 4: Gates green.**
- [ ] **Step 5: Commit** — `feat(training): verbatim artifact storage + single-shot import/activation`.

---

### Task 4: read models + routes + API types

**Files:**
- Create: `backend/app/domains/training/application/read_models.py`, `backend/app/domains/training/routes.py`
- Modify: `backend/app/domains/training/contracts.py` (view-model + log models below), `backend/app/bootstrap/routing.py` (mount `training_router`)
- Create: `backend/tests/domains/training/test_read_models.py`, `backend/tests/architecture/test_architecture_training_boundaries.py` (copy `test_architecture_programs_boundaries.py`, adjust names)
- Regenerate: `frontend/src/lib/api-types.ts`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces (contracts, all `DefaultsRequired`):

```python
class TrainingSetLog(DefaultsRequired):
    set_index: int
    weight: float | None = None
    reps: int | None = None
    rir: int | None = None


class TrainingExerciseLog(DefaultsRequired):
    exercise_id: str
    sets: list[TrainingSetLog] = []


class TrainingCheckinLog(DefaultsRequired):
    soreness: dict[str, int] = {}       # tissue -> 0..3 (attested)
    flags: dict[str, bool] = {}
    core_done: bool | None = None


class TrainingCaptureLog(DefaultsRequired):
    set_logs: list[TrainingExerciseLog] = []
    checkin: TrainingCheckinLog | None = None
    rpe: float | None = None


TrainingCardStatus = Literal["pending", "completed", "partial", "skipped"]


class TrainingCardLog(DefaultsRequired):
    id: str                              # f"{date}:{occurrence_key}"
    date: str
    occurrence_key: str                  # f"{bundle_id}:{card_id}:d{day:02d}"
    status: TrainingCardStatus = "pending"
    variant_taken: str | None = None
    notes: str | None = None
    capture: TrainingCaptureLog | None = None


class TrainingExerciseDisplay(DefaultsRequired):
    exercise_id: str
    name: str                            # from the exercise library
    scheme: str                          # "3×2–3 @ 87% e1RM"
    tempo: str | None = None
    sets: int
    log_sets: bool                       # True when card capture includes set_rep_load[]


class TrainingSegmentDisplay(DefaultsRequired):
    label: str
    detail: str                          # "7 mi · Z1-Z2"


class TrainingCheckinRow(DefaultsRequired):
    tissue: str
    label: str


class TrainingTodayCard(DefaultsRequired):
    occurrence_key: str
    date: str
    day: int
    slot: SlotName3
    bundle_id: str
    bundle_name: str
    card: V3Card                         # verbatim
    key_session: bool = False
    variants: list[Variant] = []
    rule_display: str | None = None      # omitted when clauses empty
    gate_display: str | None = None      # measurement cards: "Measurement: <estimand>. Gate: dew point (°C) <= 22; …"
    variant_options: list[str] = []      # omitted when < 2 variants
    segments_display: list[TrainingSegmentDisplay] = []
    exercises_display: list[TrainingExerciseDisplay] = []
    checkin_rows: list[TrainingCheckinRow] = []   # non-empty only for the check-in card
    capture_rpe: bool = False            # card captures a numeric RPE
    est_duration_min: float | None = None
    status: TrainingCardStatus = "pending"
    variant_taken: str | None = None
    notes: str | None = None
    capture: TrainingCaptureLog | None = None


class TrainingTodayResponse(DefaultsRequired):
    date: str
    block_id: str | None = None
    block_name: str | None = None        # block id doubles as name for now
    day: int | None = None               # None when date outside the active window
    cards: list[TrainingTodayCard] = []


class TrainingScheduleDay(DefaultsRequired):
    date: str
    day: int
    cards: list[TrainingTodayCard] = []


class TrainingScheduleWindow(DefaultsRequired):
    start_date: str
    end_date: str
    days: list[TrainingScheduleDay] = []


class TrainingBlockStatus(DefaultsRequired):
    block: V3Block
    lint_report: LintReport
    warning_acks: list[str] = []
    current_day: int | None = None
    burn_in: bool | None = None          # True during week 1
    activated_at: str
```

  - `read_models.py`: `get_training_today(repo, *, date) -> TrainingTodayResponse`, `get_training_schedule_window(repo, *, start_date, duration_days=14) -> TrainingScheduleWindow`, `get_block_status(repo) -> TrainingBlockStatus | None`, `upsert_training_log(repo, *, date, occurrence_key, update) -> TrainingCardLog` with `TrainingLogUpdateRequest` (`StrictDefaultsRequired`: `status`, `variant_taken`, `notes`, `capture`). Display projection helpers live here: `render_scheme(exercise)` ("4×5–8 @ RPE 8" — sets×reps, then pct_e1rm→`{n}% e1RM` / rpe→`RPE {n}` / absolute→`{n} kg`), `render_segment(seg)` ("7 mi · 55 min · Z1-Z2" joining distance/duration/zone-or-rpe-or-hr with " · "), `render_rule(selection)` (predicate walk to English: signal short-names `soreness.X`→"X soreness", `flag.tissue.X`→"X flag", `hrv.dev_swc`→"HRV (SWC units)", `rhr.delta_7d`→"RHR delta (bpm)", `sleep.score`→"sleep score", `env.dew_point`→"dew point (°C)", `event.*.completed`→"…already completed"; clause per line "Skip if …; otherwise full; missing data → conservative."), `checkin_rows(registry)` (tissues from `soreness.*` signal ids, label = tissue with `_`→" / "). The full-variant patch applies to displayed segments (`apply_patch` from Task 2). Date↔day: `day = (date - window.start).days + 1`, valid in `[1, window.days]`.
  - `routes.py`: `training_router = APIRouter(prefix="/api/training", tags=["training"])` — `POST /import` (body `ImportRequest`, returns `ImportResult`), `GET /today?date=`, `GET /schedule-window?start=&days=`, `GET /block` (404 via `LookupError` when none), `PUT /today/{date}/cards/{occurrence_key}`. Repo via `build_container().training_repo`, matching the routes-use-container pattern.

- [ ] **Step 1: Failing tests** — after importing block0 artifacts through `import_artifacts` inside the test (tmp DB): today for 2026-07-06 → day 1, morning contains `support.v3:sup.daily:d01` with 6 `checkin_rows` and NO `rule_display`/`variant_options` (single variant, empty clauses); today for a Tuesday (2026-07-07, day 2) contains `str.lower_a` with `variant_options == ["full","reduced","skip"]` and rule text; date before window → `day is None`, no cards; date after window end (2026-08-03) → same; boundary day 28 (2026-08-02) → cards present; upsert log (variant + one set + checkin soreness) → readback on `get_training_today` shows it; second identical upsert → unchanged (idempotent); `render_scheme`/`render_segment`/`render_rule` unit cases (pct_e1rm rounding "87% e1RM", segment join, clause English, empty-clauses → None).
- [ ] **Step 2: Verify failure.** **Step 3: Implement** (routes + read models + arch test + routing mount + container already from Task 3). **Step 4: Gates green; regen API types** (`bash scripts/generate-api-types.sh`); verify new `Training*` types appear. **Step 5: Commit** — `feat(training): today/schedule/block read models + import and capture API`.

---

### Task 5: frontend — Training Import page

**Files:**
- Create: `frontend/src/routes/training/import/+page.svelte`
- Modify: `frontend/src/lib/api.ts` (add `importTraining`, `getTrainingBlock`), `frontend/src/routes/+layout.svelte` (Training subtabs gain `{ href: '/training/import', label: 'Import' }`)

**Interfaces:** consumes Task 4's generated types (`ImportRequest`/`ImportResult`/`TrainingBlockStatus`).

- [ ] **Step 1: api.ts** — `importTraining: (body) => unwrapResponse(client.POST('/api/training/import', { body }))`, `getTrainingBlock: () => unwrapResponse(client.GET('/api/training/block'))`, following the `importProgram` pattern; re-export the types.
- [ ] **Step 2: Page.** Calm operational layout (house style, no decoration): file input (`multiple`, `.json`); selected files listed with name + detected size; client reads each with `FileReader`/`file.text()` and `JSON.parse` (parse errors shown inline per file — display-only, no interpretation); Import button POSTs `{files: [{filename, content}], warning_acks}` and renders the `ImportResult`: per-file validity with errors, `missing_kinds` notice, lint report panel (errors list, warnings list each with an "acknowledge" checkbox that adds the warning string to `warning_acks` for re-submit, weekly miles + minutes tables — tabular numerals), and on `activated=true` a success state linking to `/today`. Also show current block status via `getTrainingBlock` on load ("Active block: block0.calibration · day N of 28"; empty state: "No active block — import one."). Segmented/stable controls per UX rules.
- [ ] **Step 3:** `npm run check` → 0 errors. **Step 4: Commit** — `feat(training): import page — upload, lint report, ack, activate`.

---

### Task 6: frontend — Today/Schedule render + capture for v3 cards

**Files:**
- Create: `frontend/src/lib/training/TrainingCardBody.svelte`, `frontend/src/lib/training/TrainingStrengthGrid.svelte`, `frontend/src/lib/training/TrainingCheckinGrid.svelte`
- Modify: `frontend/src/lib/api.ts` (`getTrainingToday(date)`, `getTrainingScheduleWindow(start, days)`, `updateTrainingCard(date, key, body)`), `frontend/src/routes/today/+page.svelte`, `frontend/src/routes/routines/schedule/+page.svelte`

**Interfaces:** consumes `TrainingTodayCard`/`TrainingCaptureLog`/`TrainingLogUpdateRequest` generated types.

- [ ] **Step 1: Components.** `TrainingCardBody` props `{ card: TrainingTodayCard; mode: 'log'|'view'; onCapture?: (c: TrainingCaptureLog) => void }`: renders the `rule_display` line (muted, both modes), `gate_display` when present (measurement cards), `card.card.display_notes` when present, `segments_display` rows (label + detail), `exercises_display` via `TrainingStrengthGrid` (per-set weight/reps/RIR grid per exercise when `log_sets`, add-set button; guarded `oninput` handlers, untrack-once seed from `card.capture` — same house pattern as the Phase 0 cards), `checkin_rows` via `TrainingCheckinGrid` (0–3 chips + flag toggle per row + core checkbox, identical interaction to the Phase 0 tissue UI), and an RPE input when `capture_rpe`. Emits a full `TrainingCaptureLog` on change.
- [ ] **Step 2: Today page.** Add a training feed: fetch `api.getTrainingToday(date)` alongside `getToday` in `loadToday` (both under the same request token). Render the block's cards grouped under `block_name` within the existing slot sections (morning/midday), reusing the row chrome (checkbox/skip/expand, status, notes, variant control fed by `card.variant_options` + `card.variant_taken`); expanded panel mounts `TrainingCardBody`; persistence goes to `api.updateTrainingCard` with `{status, variant_taken, notes, capture}` (same debounce/seam patterns as the existing rows — study `persistToBackend`/`toggleComplete` before wiring; the variant-skip→status-skipped coupling carries over). Progress counter includes training cards. When BOTH feeds are empty for the date, the board's empty state links to `/training/import` ("No active block — import one").
- [ ] **Step 3: Schedule page.** Fetch `getTrainingScheduleWindow` alongside the existing window; render training occurrences per day in view mode via `TrainingCardBody mode="view"`.
- [ ] **Step 4:** `npm run check` 0 errors; existing node tests pass. **Step 5: Commit** — `feat(training): Today/Schedule render v3 cards with native capture`.

---

### Task 7: live import + visual verification + docs

**Files:**
- Modify: `README.md` (routes list + Training import section), `docs/ARCHITECTURE.md` (add a `training` module charter: Owns / Does not own / May import / Must not import / Public entrypoints — follow the existing charter format)

- [ ] **Step 1:** Start backend + frontend (env notes: `env -u NODE_OPTIONS` for background vite if needed; CORS via `BACKEND_CORS_ORIGINS` if a non-default port).
- [ ] **Step 2: THE import** (browser MCP, desktop viewport): navigate to `/training/import`, select the six files from `docs/routine-pivot/block0/` (running_v3, strength_v3, support_v3, block0, registry, exercise_library), import. Expected: all files valid, lint report **0 errors / 0 warnings**, weekly miles 49.0/49.5/49.0/32.8, activated. Screenshot the lint report.
- [ ] **Step 3: Board verification** vs `docs/routine-pivot/block0/schedule_overview.md` for the current block day (day = today − 2026-07-06 + 1): correct cards in correct slots, check-in first with 6 tissue rows, rule lines on strength/run cards, variant control (upper cards show plus), set grids with schemes, segments with distances. Capture round-trip: set a soreness, log one set with weight/reps, pick a variant, reload → all persist. Console 0 errors. Screenshots.
- [ ] **Step 4: Schedule spot-checks:** day 12 (2026-07-17) LTHR test with gate text; day 16 backup with treadmill/alternate-strides options; a week-4 day showing reduced distances.
- [ ] **Step 5: Docs** — README (new `/training/import` route, `/api/training/*` endpoints, import-only note already present), ARCHITECTURE charter. **Step 6: Full gates + commit** — `docs(training): README routes + architecture charter for the training domain`.
