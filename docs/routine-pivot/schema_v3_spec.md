# Training System v3 — Schema Specification

**Status:** Draft 1 for review
**Date:** 2026-07-04
**Governed by:** `general_principles.md` (P1–P13). Every mechanism in this spec cites the principle it operationalizes. Anything in the principles doc without a mechanism here is a spec bug.
**Notation:** Types are given in TypeScript notation for readability. The canonical wire format is JSON; JSON Schema is mechanically derivable from these definitions.

---

## 0. Pipeline

The unit of authoring is the **Bundle**. The unit of adoption is the **Block**.

```
Bundle sources ──► compile ──► CompiledSchedule ──► lint ──► adopt (event) ──► runtime
                                                     │
                                             errors block adoption;
                                             warnings require logged ack
```

Runtime, each morning: evaluate selection rules against the signal registry → select variants → log branches → athlete executes → capture → estimators update signals and state → constraints checked → weekly computed reviews → block exit evaluated against criteria.

Nothing executes from prose. If behavior isn't expressible in this schema, it doesn't exist (P5).

---

## 1. Bundles and Blocks

```ts
type SchemaVersion = "3.0";

interface Bundle {
  id: string;
  name: string;
  schema_version: SchemaVersion;
  owns: TissueTag[];               // stimulus ownership claimed by this bundle (P4)
  cards: Card[];
  assignments: Assignment[];       // day indices relative to block start
  declared_budgets?: BudgetDeclaration[];
}

interface BudgetDeclaration {
  scope: "week";
  minutes_max: number;
  minutes_min?: number;            // both checked against compiled schedule (L3)
}

type BlockIdentity = "measurement" | "development" | "consolidation" | "taper" | "race";

interface Block {
  id: string;
  identity: BlockIdentity;                 // pins purpose; content must cohere (L9)
  window: { start: string; days: number }; // ISO date
  bundle_ids: string[];
  baseline_tags: string[];                 // e.g. "heat-season", "chronic-load", "protocol-change" (P10)
  measurement_events: MeasurementEvent[];  // forcing functions (P8)
  exit_criteria: Criterion[];
  extension_rules: ExtensionRule[];        // bounded; see §8
  review_specs: ReviewSpec[];
  compiled?: CompiledSchedule;             // required for adoption
  lint_report?: LintReport;                // zero errors required for adoption
}
```

A block's identity is a contract about its content, not a label. A `measurement` block with a volume ramp is a lint error, not a style choice.

---

## 2. Cards and Stimulus Contracts (P2)

Every card carries exactly one contract. A card that cannot state its contract cannot be authored — this is where theater dies at the type level.

```ts
interface Card {
  id: string;
  bundle_id: string;
  name: string;
  contract: Contract;
  prescription: Prescription;       // the "full" definition; variants patch it
  capture: CaptureField[];          // every field must carry an AnalysisContract (P7)
  display_notes?: string;           // display-only; conditional language here is a lint error (L4)
}

type Contract =
  | OverloadContract
  | MaintenanceContract
  | MeasurementContract
  | RecoveryContract;

interface OverloadContract {
  kind: "overload";
  adaptation: "neural_force" | "tendon_stiffness" | "reactive_ability"
            | "threshold" | "vo2" | "aerobic_base" | "hypertrophy";
  progression_driver: "load" | "reps" | "contacts" | "pace" | "duration" | "density";
  state_ref: StateComponentId;      // the S component this session exists to move (P1, P6)
  ramp?: { weeks: number; endpoint: DoseSpec };
  // `ramp` is how a legitimate on-ramp differs from a hedge: it has a declared
  // endpoint the linter can see. Example: tendon HSR at RPE 6–7 for 1 week,
  // endpoint 3×4–6 @ ~85% e1RM. A ramp without an endpoint is a lint error.
}

interface MaintenanceContract {
  kind: "maintenance";
  preserves: StateComponentId;
  minimum_effective_dose: DoseSpec;
  intensity_floor: IntensityFloor;  // P3: maintenance cuts volume, never intensity.
                                    // No variant may fall below this floor (L10).
}

interface MeasurementContract {
  kind: "measurement";
  estimand: string;                 // e.g. "LTHR (bpm), current-season conditions"
  quality_gate: Predicate[];        // conditions for the data point to count
  on_fail: "retry_backup" | "flag_and_continue" | "extend_block";
}

interface RecoveryContract {
  kind: "recovery";
  load_ceiling: DoseSpec;           // recovery declares a maximum, not a suggestion
}

interface DoseSpec {                // at least one field required
  sets?: number; reps?: [number, number];
  pct_e1rm?: number; rpe_max?: number;
  contacts?: number; duration_min?: number; distance_mi?: number;
}

interface IntensityFloor {
  metric: "pct_e1rm" | "rpe" | "zone";
  min: number | string;
}
```

---

## 3. Variants and Selection Rules (P5)

Adaptivity is a policy over declared inputs, not prose. "Optional" does not exist in v3: skipping is a variant, selected by a rule, and logged.

```ts
interface Assignment {
  day: number;
  slot: "morning" | "midday" | "evening";
  card_id: string;
  key_session?: boolean;            // referenced by scheduling constraints (§6)
  variants: Variant[];              // must include exactly one with id "full"
  selection: SelectionRule;
}

interface Variant {
  id: string;                       // "full" | "reduced" | "skip" | custom
  stimulus_fraction: number;        // 1.0 for full, 0 for skip; linted (L10)
  prescription_patch?: Partial<Prescription>;
}

interface SelectionRule {
  clauses: GuardedClause[];         // ordered; first match wins
  default: string;                  // variant id under nominal signals
  on_missing_signal: "select_conservative" | "select_default" | "ask";
}

interface GuardedClause {
  when: Predicate;
  select: string;                   // variant id
}

type Predicate =
  | Cmp
  | { all: Predicate[] }
  | { any: Predicate[] }
  | { not: Predicate };

interface Cmp {
  signal: SignalId;                 // must exist in the Signal Registry (§4)
  op: "<" | "<=" | ">" | ">=" | "==" | "in";
  value: number | string | Array<number | string>;
}
```

The rule language is deliberately a decision list, not an expression language. Decision lists are auditable — the branch log records which clause fired and the full signal snapshot at evaluation time. Resist generalizing this until a real rule can't be expressed; Turing-complete policy languages are how unauditable behavior comes back in through the side door.

**Missing data is a first-class case.** Garmin syncs fail, straps die. Every rule declares what happens when its signals are stale (per staleness windows in the registry). `select_conservative` means the lowest-`stimulus_fraction` non-skip variant for overload cards and `full` for recovery cards.

---

## 4. Capture, Estimators, Signals (P6, P7, P13)

Three-stage pipeline: **CaptureField** (raw, logged at a session) → **Estimator** (model) → **Signal** (typed, consumable by rules, constraints, and state).

```ts
interface CaptureField {
  id: string;
  type: "number" | "enum" | "bool" | "set_rep_load[]";
  scale?: { min: number; max: number };   // subjective fields: small typed scales only
  contract: AnalysisContract;             // no contract → lint error (L6)
}

interface AnalysisContract {
  model_id: string;                 // the estimator this field feeds
  decision_informed: string;        // the decision the model's output changes
}

interface EstimatorDef {
  id: string;
  inputs: string[];                 // capture field ids or signal ids
  output_signal: SignalId;
  prior?: { value: number; sigma: number; source: string };
  // P13: stale knowledge enters as a wide prior, never as a cold start and
  // never as an anchor. Example: LTHR estimator carries a prior derived from
  // the 2-year-old 1:31 half with large sigma — it bounds plausibility and
  // sanity-checks the field test; it does not set zones.
}

interface SignalDef {
  id: SignalId;
  units: string;
  source: "garmin" | "derived" | "manual";
  staleness_hours: number;          // beyond this, rules treat it as missing
}
```

**Core signal registry (initial set):**

| id | units | source | notes |
|---|---|---|---|
| `hrv.dev_swc` | SWC units | derived | ln-rMSSD 7d rolling vs baseline band |
| `rhr.delta_7d` | bpm | derived | vs 28d baseline |
| `sleep.score` | 0–100 | garmin | |
| `soreness.<tissue>` | 0–3 | manual | morning check-in, one enum per owned tissue |
| `flag.tissue.<tissue>` | bool | manual | pain above background noise |
| `load.day.total` | au | derived | per-day cross-bundle rollup (§5) |
| `load.run.zone_minutes` | min[zone] | derived | primitive; scalars derive from it |
| `tonnage.<tissue>.7d` | kg | derived | from set×rep×load capture |
| `e1rm.<lift>` | kg | derived | Epley or velocity-informed later |
| `pacehr.easy_hr_at_ref_pace` | bpm | derived | heat-corrected; the interference detector |
| `env.dew_point` | °C | garmin/wx | feeds the heat-correction model — its contract |
| `event.<id>.completed` | bool | derived | measurement events as rule inputs |

The linter enforces the closure property: every capture field feeds a model, every model outputs a signal, every signal is consumed by at least one rule, constraint, state component, or review diagnostic. Orphans in either direction are errors. This is the structural ban on data theater.

---

## 5. Prescriptions, Load Capture, Ownership (P4, P6)

```ts
type Prescription =
  | RunPrescription
  | StrengthPrescription
  | ProtocolPrescription      // measurement cards: test protocols
  | RecoveryPrescription;

interface RunPrescription {
  segments: {
    label: string;
    intensity: { zone?: string; rpe?: number; hr_range?: [number, number] };
    duration_min?: number;
    distance_mi?: number;
  }[];
}

interface StrengthPrescription {
  exercises: ExercisePrescription[];
}

interface ExercisePrescription {
  exercise_id: string;              // from a normalized exercise library
  targets: TissueTag[];             // ownership-relevant: the stimulus this exists to deliver
  involves?: TissueTag[];           // rollup-relevant only: incidental load
  sets: number;
  reps: [number, number];
  load: { pct_e1rm?: number; rpe?: number; absolute_kg?: number };
  tempo?: string;
  logging: "set_rep_load";          // mandatory when any target has state coverage (L7)
}

type TissueTag =
  | "quad" | "glute" | "hamstring" | "adductor"
  | "calf_achilles" | "soleus" | "tibialis_foot"
  | "trunk_core" | "upper_push" | "upper_pull" | "grip_carry";
```

**`targets` vs `involves` is the ownership semantics.** Heavy squats involve `trunk_core`; they do not target it, so the support bundle still owns core with no conflict. Ownership (L2) is checked on `targets` only. The daily load rollup (`load.day.total` and per-tissue tonnage) sums over both. This is what makes "one tissue, one owner" workable without pretending compound lifts don't exist.

**Run-load primitive:** minutes-in-zone vector, not a proprietary scalar. Garmin's load number, TRIMP, or anything else derives from the vector; the vector is what gets stored. Scalars are opinions; the vector is data.

---

## 6. Scheduling Constraints

Structural rules the v2 system encoded as apologetic prose become declarative objects the linter checks against the compiled schedule (L5).

```ts
interface SchedulingConstraint {
  id: string;
  forbid: {
    contract_kind?: Contract["kind"][];
    targets?: TissueTag[];
  };
  relation: "within_hours_before" | "within_hours_after" | "same_day_as";
  hours?: number;
  reference: { key_session: true } | { card_id: string };
}
```

Initial set for this athlete: no `overload` targeting `hamstring | adductor` within 30 h before a `key_session` run; no strength assignment `same_day_as` the LTHR test card; at most one `overload` lower-limb card per day.

---

## 7. Measurement Events (P7, P8)

```ts
interface MeasurementEvent {
  id: string;
  card_id: string;                  // card carries the MeasurementContract + protocol
  estimand: string;
  scheduled_day: number;
  backup_days: number[];            // required non-empty when `required` (L6)
  required: boolean;
  on_all_missed: "extend_block" | "flag";
}
```

Races are measurement events with `source: external`. The tune-up half enters the system as the highest-quality anchor observation for the threshold estimator, plus a scheduled re-derivation of all zones.

---

## 8. State Vector, Objective, Constraints, Exit (P1, P8)

```ts
interface StateComponent {
  id: StateComponentId;
  description: string;
  signal: SignalId;
  estimator_id: string;
  swc: { method: "rolling_sd"; window_days: number; k: number }; // band = mean ± k·SD
}

interface ObjectiveSpec {
  progress: { state: StateComponentId; weight: number }[];  // maximize weighted dS/dt
  constraints: ConstraintSpec[];                            // recovery lives HERE, not above
}

interface ConstraintSpec {
  signal: SignalId;
  band: { lo?: number; hi?: number };
  on_violation: {
    action: "select_conservative_variants" | "insert_recovery_day" | "flag_review";
    scope: "next_day" | "next_3_days";
  };
}

interface Criterion {                // block exit criteria
  id: string;
  predicate: Predicate;              // over signals, incl. event.*.completed
}

interface ExtensionRule {
  when_failed: string;               // criterion id
  action: { extend_days: number; insert?: MeasurementEvent };
  cap_total_extension_days: number;  // extensions are bounded — "more measurement
                                     // needed" is the recovery-maximizer's favorite
                                     // costume, and the cap is the counter (P1, P8)
}
```

**Concrete state vector for this athlete (initial):** `S1 threshold_pace_at_lthr` (heat-corrected), `S2 e1rm.squat_pattern`, `S3 e1rm.calf_soleus_hsr`, `S4 upper_physique_proxy` (upper tonnage trend + bodyweight). Every component has capture scheduled in every block, or L7 fires.

---

## 9. Reviews (P12)

```ts
interface ReviewSpec {
  cadence: "weekly" | "block_end";
  computed: { id: string; estimator_id: string }[];  // machine answers these
  human_prompts: string[];                           // residual only
}
```

Computed diagnostics for Block 0: `interference_check` (next-morning `pacehr.easy_hr_at_ref_pace` contrasted by prior-day session targets), `contamination_check` (strap-data validity fraction per week), `hsr_tolerance` (soreness.calf_achilles trajectory across first exposures). Human prompts are reserved for what sensors can't see: mechanics feel, motivation, niggles-not-yet-flags.

---

## 10. Event Log

Append-only. Minimum event types:

```ts
type Event =
  | { t: "branch_taken"; at: string; assignment: Ref; signal_snapshot: Record<SignalId, number>; clause_index: number; variant: string }
  | { t: "manual_override"; at: string; assignment: Ref; selected_by_rule: string; executed: string; reason: string }
  | { t: "protocol_change"; at: string; description: string }        // P10
  | { t: "measurement_outcome"; at: string; event_id: string; passed_gate: boolean; value?: number }
  | { t: "lint_run"; at: string; block_id: string; errors: number; warnings: number; acks: string[] }
  | { t: "block_adopted" | "block_exit"; at: string; block_id: string; criteria_state: Record<string, boolean> };
```

Manual override is always available and never silent: the athlete outranks the rule, the log outranks memory. Override frequency is itself a diagnostic — a rule overridden weekly is a wrong rule.

---

## 11. Validator

Errors block adoption. Warnings require a logged ack.

| id | severity | check | principle |
|---|---|---|---|
| L1 | error | every card has exactly one well-formed contract; kind-required fields present | P2 |
| L2 | error | no `TissueTag` appears in `targets` of cards from two bundles active in one block | P4 |
| L3 | error | compiled per-week durations within every `BudgetDeclaration` | P11 |
| L4 | error | `display_notes` free of conditional/coordination language (`if / unless / only / skip / instead / optional`) | P5 |
| L5 | error | all `SchedulingConstraint`s satisfied on the compiled schedule | P11 |
| L6 | error | required events have backups; every capture field has an `AnalysisContract`; signal closure holds (no orphan fields, models, or signals) | P7, P8 |
| L7 | error | every `StateComponent` has ≥1 scheduled capture in the block | P6 |
| L8 | error | every prescription resolves to the daily load rollup (no unparseable load) | P11 |
| L9 | error | content coheres with `identity` (measurement ⇒ run volume flat within ±3%, no unramped novel overload; development ⇒ ≥1 overload contract per declared progress term) | P8 |
| L10 | error | anti-theater: default-path variant is `full`; overload/maintenance non-skip variants keep `stimulus_fraction ≥ 0.5`; maintenance variants never breach `intensity_floor`; `ramp` has endpoint; no card is skippable except via a logged rule | P2, P3 |
| L11 | warning | >2 novel protocol elements in week 1 without matching `baseline_tags` | P10 |
| L12 | error | block declares `exit_criteria` + bounded `extension_rules` (mandatory for `measurement` identity) | P8 |

**v2 autopsy under this linter** — every rule fires: day-9 loaded-vs-bodyweight calf duplication (L2); support budget declared 20–45 min, scheduled 55–69 (L3); day-12 contradictory cross-bundle prose (L4); RDLs 24 h before the long run (L5); LTHR optional, dew point feeding nothing (L6); zero strength state capture (L7); no daily aggregate (L8); a 5% ramp inside a "calibration" block and a deload from ≤ baseline (L9); six stacked hedges and "optional" tags (L10); dual new baselines in week 1 (L11); no exit criteria (L12). A schema under which the previous system cannot be expressed is the point.

---

## 12. Worked Examples

**A — Lower A (neural force) with variants and a selection rule:**

```json
{
  "card": {
    "id": "str.lower_a", "bundle_id": "strength.v3", "name": "Lower A — Neural Force",
    "contract": {
      "kind": "overload", "adaptation": "neural_force",
      "progression_driver": "load", "state_ref": "S2"
    },
    "prescription": { "exercises": [{
      "exercise_id": "machine_squat", "targets": ["quad", "glute"],
      "involves": ["trunk_core"], "sets": 3, "reps": [2, 3],
      "load": { "pct_e1rm": 0.87, "rpe": 8 }, "logging": "set_rep_load"
    }]},
    "capture": [{ "id": "set_log", "type": "set_rep_load[]",
      "contract": { "model_id": "e1rm.squat_pattern", "decision_informed": "load progression; S2 trend" } }]
  },
  "assignment": {
    "day": 2, "slot": "midday", "card_id": "str.lower_a",
    "variants": [
      { "id": "full", "stimulus_fraction": 1.0 },
      { "id": "reduced", "stimulus_fraction": 0.6,
        "prescription_patch": { "exercises": [{ "sets": 2, "load": { "pct_e1rm": 0.85 } }] } },
      { "id": "skip", "stimulus_fraction": 0 }
    ],
    "selection": {
      "clauses": [
        { "when": { "any": [ { "signal": "flag.tissue.quad", "op": "==", "value": true },
                             { "signal": "hrv.dev_swc", "op": "<", "value": -1.5 } ] },
          "select": "skip" },
        { "when": { "signal": "hrv.dev_swc", "op": "<", "value": -0.75 }, "select": "reduced" }
      ],
      "default": "full",
      "on_missing_signal": "select_conservative"
    }
  }
}
```

**B — LTHR test as a required measurement event:**

```json
{
  "id": "ev.lthr_test", "card_id": "run.lthr_field_test",
  "estimand": "LTHR (bpm), heat-season conditions",
  "scheduled_day": 12, "backup_days": [15], "required": true,
  "on_all_missed": "extend_block"
}
```
with the card's contract: `{ "kind": "measurement", "estimand": "LTHR (bpm)", "quality_gate": [ {"signal": "strap.validity_pct", "op": ">=", "value": 0.95}, {"signal": "env.dew_point", "op": "<", "value": 24} ], "on_fail": "retry_backup" }`.

**C — Block 0 exit criteria and bounded extension:**

```json
{
  "exit_criteria": [
    { "id": "lthr_anchored", "predicate": { "signal": "event.ev.lthr_test.completed", "op": "==", "value": true } },
    { "id": "two_clean_cycles", "predicate": { "signal": "weeks.flat_valid_count", "op": ">=", "value": 2 } },
    { "id": "e1rm_initialized", "predicate": { "all": [
        { "signal": "e1rm.squat_pattern", "op": ">", "value": 0 },
        { "signal": "e1rm.calf_soleus_hsr", "op": ">", "value": 0 } ] } },
    { "id": "heat_model_first_fit", "predicate": { "signal": "model.heat_correction.fitted", "op": "==", "value": true } }
  ],
  "extension_rules": [
    { "when_failed": "lthr_anchored", "action": { "extend_days": 7 }, "cap_total_extension_days": 14 },
    { "when_failed": "two_clean_cycles", "action": { "extend_days": 7 }, "cap_total_extension_days": 14 }
  ]
}
```

**D — HSR on-ramp as a declared ramp, not a hedge:**

```json
{ "kind": "overload", "adaptation": "tendon_stiffness", "progression_driver": "load",
  "state_ref": "S3",
  "ramp": { "weeks": 1, "endpoint": { "sets": 3, "reps": [4, 6], "pct_e1rm": 0.85 } } }
```

---

## 13. Open Decisions

1. **e1RM estimator:** Epley from logged sets is the day-1 default; velocity-based later if hardware appears. Decision needed only on the formula, not the interface.
2. **SWC band parameters:** proposed default ln-rMSSD rolling mean ± 0.5·SD over 7 d against a 28 d baseline; tune after Block 0 — this is exactly what Block 0's flat weeks are for.
3. **Heat-correction model form:** start linear in dew point on the HR-at-reference-pace residual; July-only data cannot validate it (no cool support) — first honest fit lands after the fall re-anchor.
4. **Predicate language extensibility:** hold the line at decision lists until a real rule is inexpressible. Log the failed attempt before extending the language.
5. **Exercise library normalization:** flat namespace with per-exercise tissue tags; needed before bundle authoring, trivial to produce.
6. **Where estimators run:** nightly batch after Garmin sync; morning rule evaluation reads only materialized signals. Keeps runtime dumb and auditable.

---

## Definition of done for this spec

Bundles for Block 0 can be authored against §1–§7 with no field left to interpretation; the linter is implementable from §11 alone; and the v2 bundles, translated honestly, fail compilation. When all three hold, the spec is frozen as v3.0 and bundle authoring starts.
