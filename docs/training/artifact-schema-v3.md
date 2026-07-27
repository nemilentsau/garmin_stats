# Training System v3 Artifact Contract

**Status:** shipped as schema version `3.0`.

This document is the semantic authoring contract. The executable wire models live in `backend/app/domains/training/contracts.py`, the L1-L12 activation policy lives in `backend/app/domains/training/application/validation.py`, and imported JSON is stored verbatim. The app adapts directly to authored v3 artifacts; uploaded content is never translated into another runtime format.

The governing behavior is in [`principles.md`](principles.md). Current implementation gaps belong in [`roadmap.md`](roadmap.md), not in this schema reference.

## Repository artifacts

- [`threshold-development-2026-07-13.zip`](programs/threshold-development-2026-07-13/threshold-development-2026-07-13.zip) is the latest authored program retained in the repository and the exact file accepted by the import surface. Its six JSON artifacts exist only as members of that package; repository presence does not imply runtime activation.
- `backend/tests/fixtures/training/v3-calibration/` contains the read-only calibration artifacts and expected lint report used by contract, validator, import, and read-model tests.
- `lint_report.json` and compiled schedules are outputs, not content ingress. The runtime compiles and lints an upload during activation and persists the resulting report with the active block.

## Import set and lifecycle

One import is an authored ZIP package. The backend reads JSON members in memory,
ignores non-JSON documentation and platform metadata, and never extracts or
rewrites package content. The JSON members contain exactly:

1. every bundle named by the block's `bundle_ids` (currently `running_v3.json`, `strength_v3.json`, and `support_v3.json`);
2. one block definition (`block1.json` in the latest authored program);
3. one `registry.json`;
4. one `exercise_library.json`.

The import request also requires an explicit runtime start date. The server
bounds the compressed package, member count, and decompressed JSON size before
it strictly validates each JSON object. It checks that the set is complete and
internally consistent, compiles the schedule, runs L1-L12, requires
acknowledgement of any warnings, then atomically retires the prior generation
and activates the new one. The chosen date is stored as activation metadata and
defines Day 1 for runtime projections; no ZIP member is rewritten. A failed
import writes nothing.

## Artifact models

All models reject unknown fields. Fields with defaults remain required in the serialized JSON schema, so authors should write them explicitly.

### Bundle

`V3Bundle` contains:

- `id`, `name`, `schema_version: "3.0"`;
- `owns`: target tissues owned by this bundle;
- `cards`: reusable `V3Card` definitions;
- `assignments`: day-relative scheduled uses of those cards;
- `declared_budgets`: weekly minimum/maximum minutes checked by the linter.

### Card and contract

`V3Card` contains `id`, `bundle_id`, `name`, exactly one discriminated `contract`, one `prescription`, `capture`, optional `display_notes`, and optional `est_duration_min`.

The four contract kinds are:

| Kind | Required meaning |
|---|---|
| `overload` | adaptation, progression driver, state component, and optional bounded ramp |
| `maintenance` | preserved state, minimum effective dose, and intensity floor |
| `measurement` | estimand, quality-gate predicates, and failure policy |
| `recovery` | maximum permitted dose |

`display_notes` is explanatory only. Conditional or cross-bundle coordination language belongs in variants, selection rules, or scheduling constraints and is rejected by L4.

### Prescription

The wire union has two shapes:

- `SegmentPrescription`: ordered `segments`, each with `label`, `intensity` (`zone`, `rpe`, or `hr_range`) and optional `duration_min` / `distance_mi`;
- `StrengthPrescription`: ordered `exercises`, each with `exercise_id`, `targets`, optional `involves`, `sets`, repetition range, load (`pct_e1rm`, `rpe`, or `absolute_kg`), optional tempo, and `logging: "set_rep_load"`.

Running, support, recovery, and measurement protocols all use the segment shape. The runtime distinguishes tracked-run association by bundle id (`running.v3`), not merely by prescription shape.

### Capture

Each capture field has an `id`, a type (`number`, `enum`, `bool`, or `set_rep_load[]`), an optional numeric scale, and an analysis contract containing `model_id` plus `decision_informed`.

Capture ids and estimator inputs must close over the registry. A field without a registered consumer or a registered signal without a consumer is an activation error.

### Assignment, variant, and selection

`V3Assignment` contains:

- `day` (1-based within the block), `slot`, `card_id`, and `key_session`;
- `variants`, including `full`; each declares `stimulus_fraction` and may carry a partial prescription patch;
- `selection`, an ordered decision list with `clauses`, a `default` variant, and `on_missing_signal` policy.

The current runtime displays this policy and records the athlete's chosen `variant_taken`; automated rule evaluation remains future work. A manual choice never modifies the artifact.

Predicates are recursive comparisons: a leaf is `{signal, op, value}` and composite nodes are `{all: [...]}`, `{any: [...]}`, or `{not: ...}`. Supported operators are `<`, `<=`, `>`, `>=`, `==`, and `in`.

### Block

`V3Block` contains:

- `id`, optional human-facing `name`, `identity`, `window`, and `bundle_ids`;
- `baseline_tags`, `flat_weeks`, and optional `step_response`;
- `measurement_events` with scheduled and authored backup days;
- `scheduling_constraints`;
- `exit_criteria`, bounded `extension_rules`, and `review_specs`.

Valid identities are `measurement`, `development`, `consolidation`, `taper`, and `race`. The identity is a contract evaluated by lint policy, not a display label.

`window.start` records the author's planned/provenance date. `window.days` and
assignment day numbers remain authoritative program-relative content. Runtime
calendar placement comes from the explicit Day 1 selected during import, which
is stored outside the artifact. Existing stored records without runtime start
metadata fall back to `window.start` for compatibility.

Measurement backup days are authored opportunities. The runtime may overlay the original measurement card into an existing running slot when prior attempts have not qualified; it never creates dates, rewrites the compiled schedule, or persists a derived bundle.

### Signal registry

`SignalRegistry` contains:

- typed signals with `id`, `units`, `source`, and `staleness_hours`;
- estimators with input ids, one output signal, and an optional prior;
- state-vector components with signal, estimator, and smallest-worthwhile-change definition;
- the weighted progress objective and constraint actions.

The registry is currently validated and stored but is only partially executed. Do not describe a declared signal as materialized unless an application read path actually computes and persists it.

### Exercise library

`ExerciseLibrary` maps stable exercise ids to names plus `targets` and `involves` tags. Bundle prescriptions reference these ids. The current wire model accepts string tags; ownership consistency is enforced by the block linter.

## L1-L12 activation checks

| Rule | Current check |
|---|---|
| L1 | assignment/card references and contract state references resolve |
| L2 | bundle tissue ownership is unique and targeted tissues use their owner |
| L3 | compiled weekly minutes satisfy declared budgets |
| L4 | display notes contain no conditional/coordination policy |
| L5 | authored scheduling constraints hold |
| L6 | required measurement backups, estimator/capture references, and signal closure hold |
| L7 | every state estimator transitively reaches capture scheduled in the block |
| L8 | every prescription resolves to load units |
| L9 | measurement-block flatness and novel tendon-ramp constraints hold |
| L10 | assignments have an adequate full/default path and no under-dosed non-skip variant |
| L11 | more than two week-one overload adaptations require `protocol-change` context |
| L12 | every block has exit criteria; measurement blocks also have bounded extensions |

Pydantic validation owns required-field/type checks that cannot reach the linter. The linter owns cross-object and compiled-schedule invariants.

## Runtime ownership

- Imported block, bundle, registry, and exercise-library JSON remains verbatim in storage.
- Runtime activation metadata owns the selected Day 1 and never mutates
  `window.start`.
- Compiled schedules and display projections are read models, not authored content.
- Training capture logs own status, variant, notes, set logs, check-ins, run link state, and subjective RPE.
- Garmin Analytics owns tracked-run storage and display; Training reads it through an injected local port.
- Coach owns subjective measurement assessments; Training owns objective observations, quality gates, retries, backup opportunities, and estimator eligibility.
- The frontend never interprets predicates or computes training statistics.
