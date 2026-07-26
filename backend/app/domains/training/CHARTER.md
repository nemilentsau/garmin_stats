# training — Charter

**Status:** shipped
**Boundary source of truth for this slice. Update in the same PR that changes it.**

The v3-native training runtime. Its HTTP boundary accepts one authored ZIP package, decodes the contained JSON artifacts in memory, lint-gates and single-shot activates them, compiles their schedule, and projects execution, measurement, and authored backup state into Today / schedule-window / block-status read models plus per-occurrence capture logs. The import endpoint is the ONLY ingress for training content: artifacts are stored without translation, and runtime projections never create or rewrite authored content.

## Owns

- bounded, in-memory v3 ZIP package decoding plus single-shot atomic activation
  of its content bundles, block definition, signal registry, and exercise library.
- The ported L1-L12 block linter.
- Schedule compilation from imported bundles.
- Today / schedule-window / block-status read models.
- Effective execution and measurement projection from training-local run
  evidence, including pure quality-gate evaluation, Coach-result
  finalization, estimator eligibility, and required-retry state.
- Pure read-time overlay of authored measurement backup days and exhausted
  event actions. It may substitute the original measurement card into an
  existing running slot; it never edits the compiled schedule or artifact.
- Per-occurrence capture-log persistence (set/rep/load logs, RPE, variant
  selection, check-in tissue soreness/flags, and run-card link state
  `linked_run_id`/`run_link_detached`).
- The import endpoint is the ONLY ingress for training content: artifacts are
  stored verbatim, and nothing else in the app may create or derive training
  rows.
- The run<->prescription association read policy (`match_run_to_card`):
  which tracked run, if any, a scheduled `running.v3` card displays as
  executed on Today and schedule-window. Training defines the
  `RunActivityReadPort` summary/full-evidence contract and the
  `MeasurementAssessmentReadPort` projection it reads through, but sees
  Garmin and Coach data only through those injected ports.
- Runtime occurrence resolution shared by reads and writes. Activated
  backups receive stable event-qualified keys; capture writes resolve the
  same Today overlay so active keys are writable and inactive keys are not.

## Does not own

- Experiment analysis.
- Garmin ingest.
- Garmin run persistence or canonical FIT contracts.
- Coach assessment persistence or model-output validation.
- Mutation, generation, translation, or rescheduling of imported content.

The frontend Today and schedule pages render the v3 training feed alone;
there is no separate routines feed to compose it with.

## May import

- Same-slice contracts, domain/application modules, and dependency protocols.
- Standard-library and Pydantic primitives, plus shared base/time helpers from
  `app.contracts.base` and `app.utils.timeutil`.
- Training-owned persistence boundaries (`adapters.py` and `schema.py`) may
  use the shared `app.infra.jsonstore` and `app.infra.sqlite` primitives.
- The route module may import FastAPI and the bootstrap container to bind
  injected dependencies; bootstrap owns cross-domain adapter composition.

## Must not import

- experiments, journal, coach, Garmin sync, Garmin analytics, Garmin health,
  FastAPI from application modules, or SQLite helpers from application
  modules.
- Application/domain policy must not import bootstrap or infrastructure;
  persistence remains behind `TrainingRepository`.
- Tracked-run summaries/full evidence and Coach judgments go through the
  injected training-local ports only. Their concrete adapters and wiring
  live in bootstrap; training never imports either source domain's contract
  or persistence adapter.

## Public entrypoints

- `POST /api/training/import`
- `GET  /api/training/today`
- `GET  /api/training/schedule-window`
- `GET  /api/training/block`
- `PUT  /api/training/today/{date}/cards/{occurrence_key}`
- Import/activation use cases and Today/schedule-window/block-status read-model
  use cases.

## Key files

- `routes.py` — FastAPI binding for the five `/api/training` endpoints; resolves
  dependencies from the container, delegates training policy to the application
  layer, and persists capture updates without triggering Coach work.
- `application/import_packages.py` — `ImportPackageRequest` and `import_package`:
  safely decode one bounded ZIP into JSON artifacts, then delegate without
  extracting files, translating content, or owning artifact validation.
- `application/imports.py` — `import_artifacts` (+ `ImportRequest` /
  `ImportResult`): validate → lint → single-shot activate an uploaded v3
  artifact set after package decoding.
- `application/validation.py` — the ported L1-L12 block linter (all of L1
  through L12 present); blocks activation on failure.
- `application/compile.py` — `compile_schedule` and `full_variant_prescription`:
  schedule compilation from imported bundles.
- `application/read_models.py` — `get_training_today`,
  `get_training_schedule_window`, `get_block_status`, and `upsert_training_log`
  (PATCH-semantics capture-log upsert with runtime occurrence validation),
  plus orchestration of association, measurement evidence, exact assessment
  lookup with optional historical cutoffs, request snapshots, and frozen
  authored-opportunity history.
- `domain/run_evaluation.py` — pure effective-execution, LTHR observation,
  quality-gate, and Coach-finalization policy.
- `application/measurement_schedule.py` — pure read-time activation of
  authored backup opportunities and exhausted-event actions.
- `contracts.py` — v3 wire contracts for imported training artifacts,
  the `LintReport` output contract, `Stored{Bundle,Block,Registry,Library}`
  persistence envelopes, the `TrainingCardLog` capture record (incl.
  `linked_run_id`/`run_link_detached`), the training-local
  run summary/full-evidence and Coach-assessment projections,
  and the `Training*` display/response/window view models.
- `dependencies.py` — `TrainingRepository` protocol (the single persistence
  dependency for import, activation, and capture use cases),
  `RunActivityReadPort`, and `MeasurementAssessmentReadPort`; both read ports
  are implemented outside the slice.
- `adapters.py` — `SqliteTrainingRepository`: the persistence boundary; owns the
  single-active-block/bundle retire-then-activate transaction.
- `schema.py` — five jsonstore tables (`training_bundles`, `training_blocks`,
  `training_registry`, `training_exercise_library`, `training_card_logs`).

The concrete association, LTHR evaluation, and backup semantics live in
`docs/reference/run-activities.md`; this charter owns only the domain boundary.
