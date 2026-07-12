# training — Charter

**Status:** shipped
**Boundary source of truth for this slice. Update in the same PR that changes it.**

The v3-native training runtime. It imports authored v3 training artifacts, lint-gates and single-shot activates them, compiles a schedule from the imported bundles, and serves the Today / schedule-window / block-status read models plus per-occurrence capture logs. The import endpoint is the ONLY ingress for training content: artifacts are stored verbatim, and nothing else in the app may create or derive training rows. On the frontend, the Today and schedule pages compose the training feed and the routines feed side by side; neither domain imports the other.

## Owns

- v3 training artifact import and single-shot atomic activation (content
  bundles, block definition, signal registry, exercise library).
- The ported L1-L12 block linter.
- Schedule compilation from imported bundles.
- Today / schedule-window / block-status read models.
- Per-occurrence capture-log persistence (set/rep/load logs, RPE, variant
  selection, check-in tissue soreness/flags, and run-card link state
  `linked_run_id`/`run_link_detached`).
- The import endpoint is the ONLY ingress for training content: artifacts are
  stored verbatim, and nothing else in the app may create or derive training
  rows.
- The run<->prescription association read policy (`match_run_to_card`):
  which tracked run, if any, a scheduled `running.v3` card displays as
  executed, on the Today view only. Training defines this policy and the
  `RunActivityReadPort` Protocol/`TrainingRunActivitySummary` contract it
  reads through, but never sees a tracked run except via that injected
  port — see "Must not import".

## Does not own

- Routine catalog or activation for non-training routines.
- Assistant artifact staging.
- Experiment analysis.
- Program import.
- Garmin ingest.
- Garmin analytics.

The frontend Today and schedule pages compose the training feed and the
routines feed side by side; neither domain imports the other.

## May import

- Its own contracts, application helpers, and dependencies.

## Must not import

- routines, experiments, assistant, artifacts, journal, programs, Garmin sync,
  Garmin analytics, FastAPI from application modules, or SQLite helpers from
  application modules.
- Persistence goes through `app.infra.jsonstore` only, via `adapters.py`.
- Tracked-run data for association goes through the injected
  `RunActivityReadPort` only — never a direct `garmin_analytics`/
  `garmin_health` import. The concrete adapter (`GarminRunActivityPort`,
  wrapping `garmin_analytics`'s runs repository) and its wiring live outside
  this slice, in `backend/app/bootstrap/run_activity_port.py` and
  `bootstrap/container.py` — bootstrap is not a slice, so this composition
  needs no cross-slice allowlist entry.

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
  `training_repo` from the container and delegates all policy to the application
  layer (only local behavior is the "no active block" → 404 fallback).
- `application/imports.py` — `import_artifacts` (+ `ImportRequest` /
  `ImportResult`): validate → lint → single-shot activate an uploaded v3
  artifact set.
- `application/validation.py` — the ported L1-L12 block linter (all of L1
  through L12 present); blocks activation on failure.
- `application/compile.py` — `compile_schedule` and `full_variant_prescription`:
  schedule compilation from imported bundles.
- `application/read_models.py` — `get_training_today`,
  `get_training_schedule_window`, `get_block_status`, and `upsert_training_log`
  (PATCH-semantics capture-log upsert with occurrence validation), plus the
  pure `match_run_to_card` run<->prescription association policy that
  `get_training_today` (only) threads through `_cards_for_day`/`_build_card`
  when a `RunActivityReadPort` is supplied.
- `contracts.py` — v3 wire contracts (parse the read-only Block 0 artifacts),
  the `LintReport` output contract, `Stored{Bundle,Block,Registry,Library}`
  persistence envelopes, the `TrainingCardLog` capture record (incl.
  `linked_run_id`/`run_link_detached`), the training-local
  `TrainingRunActivitySummary` run projection, and the `Training*`
  display/response/window view models.
- `dependencies.py` — `TrainingRepository` protocol (the single persistence
  dependency for import, activation, and capture use cases) and
  `RunActivityReadPort` (read-only tracked-run access for association,
  implemented outside the slice — see "Must not import").
- `adapters.py` — `SqliteTrainingRepository`: the persistence boundary; owns the
  single-active-block/bundle retire-then-activate transaction.
- `schema.py` — five jsonstore tables (`training_bundles`, `training_blocks`,
  `training_registry`, `training_exercise_library`, `training_card_logs`).

## Verified against code (2026-07-10; association re-checked 2026-07-12)

matches — with one clarifying note that is not a violation:

- Owns: confirmed. Import + single-shot activation (`imports.import_artifacts`,
  `adapters.save_import` retire-then-activate in one transaction); L1-L12 linter
  (`validation.py` — L1 through L12 codes all present); schedule compilation
  (`compile.compile_schedule`); Today/schedule-window/block-status read models
  (`read_models.get_training_today` / `get_training_schedule_window` /
  `get_block_status`); capture-log persistence (`read_models.upsert_training_log`,
  `TrainingCardLog`, five jsonstore tables incl. `training_card_logs`).
- Public entrypoints: all five `/api/training/*` routes present in `routes.py`
  with the exact paths listed; use cases exported as named above.
- Must not import: confirmed. No imports of routines, experiments, assistant,
  artifacts, journal, programs, garmin_sync, or garmin_analytics anywhere in the
  slice. FastAPI appears only in `routes.py` (route module — allowed by the
  slice boundary convention), never in `application/`. `sqlite3` /
  `app.infra.sqlite.connect` appear only in `adapters.py` and `schema.py`
  (the persistence boundary), never in application modules; application modules
  depend on the `TrainingRepository` protocol from `dependencies.py`.
- Clarifying note (not a discrepancy): the charter's "May import" line lists
  only slice-owned things, but the code also imports the globally-allowed shared
  primitives — `app.contracts.base` (response bases), `app.utils.timeutil`
  (`now_iso`), and `app.infra.jsonstore` / `app.infra.sqlite` (persistence, via
  `adapters.py`/`schema.py`), plus `app.bootstrap.container.build_container` in
  the route module. These are governed by the global Slice Boundary Convention
  and the dependency-direction rules in `docs/ARCHITECTURE.md`, and the
  "Must not import" clause explicitly permits `app.infra.jsonstore`, so they are
  in-bounds.
- Association re-check (2026-07-12, after `74bd5a9`/`982fc0c` landed): `match_run_to_card`'s
  manual-wins/detach/auto-single-card-closest-distance precedence, `_is_run_card`'s
  `running.v3` discriminator, `GET /today`-only threading of `run_activity_port` (confirmed
  absent from `get_training_schedule_window`), and the PATCH-only-if-present semantics of
  `linked_run_id`/`run_link_detached` on `TrainingLogUpdateRequest` all match this charter's
  "Owns"/"Key files" description exactly — no drift found. Full policy write-up, with the
  `RunActivityReadPort`/`GarminRunActivityPort` port boundary, lives in
  `docs/reference/run-activities.md` ("Association").
