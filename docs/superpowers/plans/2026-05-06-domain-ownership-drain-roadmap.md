# Domain Ownership Drain Roadmap

> **For agentic workers:** This is a sequencing roadmap, not a single execution
> batch. Before implementing any phase, write a focused phase plan using
> `superpowers:writing-plans`, then execute it with `superpowers:subagent-driven-development`
> or `superpowers:executing-plans`. Do not run multiple phases in one commit.

**Goal:** Drain `app.models`, `app.stats`, and `app.infra.database` into clear
owned modules while preserving API behavior and avoiding new generic shared buckets.

**Architecture:** Treat Garmin analytics as the foundational read-model layer,
then clean domains in dependency order: routines before experiments, experiments
before assistant and programs. Shared functionality may be extracted only when it
is domain-neutral mechanics used by at least two owners.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, ruff, pyright, generated
OpenAPI TypeScript types.

---

## Dependency Order

Use this order unless a feature forces a narrower opportunistic extraction:

1. `domains/garmin_analytics`
2. `domains/routines`
3. `domains/experiments`
4. `domains/assistant`
5. `domains/artifacts`
6. `domains/programs`
7. remaining small slices such as `core/profile` and `domains/journal`

Rationale:

- Garmin analytics is foundational read-model infrastructure for recovery,
  metrics, and assistant evidence.
- Experiments depend on routine schedule/exposure semantics, so routines go first.
- Assistant depends on experiments and analytics evidence, so it follows them.
- Programs should follow routines and experiments because future program
  activation will compose those domains.
- Journal and profile are good opportunistic extractions, but they do not unblock
  the larger dependency cleanup.

## Shared-Code Rule

Extract shared code only when all of these are true:

- At least two domains use the exact same mechanical behavior.
- The behavior has no Garmin, experiment, routine, assistant, or artifact semantics.
- The extraction shrinks an import allowlist or removes repeated SQLite/math
  mechanics from domain files.
- The extracted module name describes mechanics, not product meaning.

Allowed shared candidates:

- SQLite connection/transaction helpers.
- JSON record save/load row mechanics.
- Timestamp stamping and JSON model hydration helpers.
- Numeric primitives such as safe average, median, percentile.

Disallowed shared candidates:

- HR zones, HRV status, period summaries, Garmin baselines, recovery scoring.
- Experiment exposure policy, adherence semantics, routine occurrence rules.
- Assistant evidence assembly or entity resolution.
- Generic repository frameworks that hide table ownership.

## Phase 0: Guardrail Inventory

**Purpose:** Make the current shared-bucket imports measurable before moving code.

**Files:**

- Modify: `backend/tests/architecture/test_architecture_global_ownership.py`
- Modify: `backend/tests/architecture/test_architecture_cross_slice_imports.py`
- Optional create: `backend/tests/architecture/test_architecture_model_contracts.py`

**Steps:**

- [ ] Add allowlists for current `app.models`, `app.stats`, and `app.infra.database`
      importers by file.
- [ ] Run `cd backend && uv run pytest tests/architecture -v`.
- [ ] Commit with `test: document current shared ownership imports`.

**Exit criteria:**

- Architecture tests make current shared-bucket imports visible.
- Future phases can prove cleanup by shrinking allowlists.

## Phase 1: Garmin Analytics Foundation

**Purpose:** Move Garmin-owned stats and database read behavior behind the
Garmin analytics slice before downstream domains depend on cleaner contracts.

**Files:**

- Modify: `backend/app/stats.py`
- Modify: `backend/app/domains/garmin_analytics/application/*.py`
- Modify: `backend/app/domains/garmin_analytics/application/ports.py`
- Modify: `backend/app/domains/garmin_analytics/infra/biometric_repository.py`
- Modify: `backend/app/infra/database.py`
- Test: `backend/tests/domains/garmin_analytics/test_stats.py`
- Test: `backend/tests/domains/garmin_analytics/test_*analysis*.py`
- Test: `backend/tests/architecture/test_architecture_global_ownership.py`

**Steps:**

- [ ] Classify each `app.stats` function as generic numeric primitive or Garmin
      analytics behavior.
- [ ] Move Garmin behavior into `domains/garmin_analytics/application/` modules.
- [ ] Keep only truly generic numeric primitives in a small shared module if at
      least two domains use them.
- [ ] Move Garmin biometric read helpers from `app.infra.database` behind
      `SqliteBiometricRepository` or smaller repository-owned primitives.
- [ ] Shrink the `app.stats` and `app.infra.database` architecture allowlists.
- [ ] Run `cd backend && uv run ruff check app/ tests/`.
- [ ] Run `cd backend && uv run pyright app/ tests/`.
- [ ] Run `cd backend && uv run pytest tests/ -v`.
- [ ] Commit with `refactor: tighten Garmin analytics ownership`.

**Exit criteria:**

- Garmin analytics application modules no longer depend on broad `app.stats`
  except for explicitly shared numeric primitives.
- Garmin analytics reads go through its repository boundary.
- No OpenAPI shape changes unless an intentional contract move is included.

## Phase 2: Routines Before Experiments

**Purpose:** Stabilize routine schedule, Today, and card-log ownership before
experiment exposure derivation builds on those rules.

**Files:**

- Create: `backend/app/domains/routines/contracts.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/domains/routines/**/*.py`
- Modify: `backend/app/domains/artifacts/application/artifacts.py`
- Modify: `backend/app/domains/experiments/application/exposure_sync.py`
- Modify: `backend/app/domains/routines/infra/sqlite_repository.py`
- Modify: `backend/app/infra/database.py`
- Test: `backend/tests/domains/routines/*.py`
- Test: `backend/tests/domains/artifacts/test_artifact_bundles.py`
- Test: `backend/tests/domains/experiments/test_experiment_exposure_sync.py`

**Steps:**

- [ ] Move routine, schedule, Today, card-log, and card-override contracts to
      `domains/routines/contracts.py` when touched.
- [ ] Keep artifact bundle/card-template contracts in artifacts, not routines,
      unless a model is part of live Today/runtime behavior.
- [ ] Move routine SQLite functions behind `SqliteRoutineRepository` or a
      repository-owned helper.
- [ ] Update experiments to consume routine ports/contracts, not `app.models`
      routine symbols directly.
- [ ] Regenerate API types if OpenAPI ordering or schemas change:
      `bash scripts/generate-api-types.sh`.
- [ ] Run backend lint, pyright, and tests.
- [ ] Run `cd frontend && npm run check` if API types changed.
- [ ] Commit with `refactor: tighten routine ownership`.

**Exit criteria:**

- Experiments depend on routine ports/contracts for exposure-related routine data.
- Routine models are no longer a broad `app.models` dependency for migrated code.
- Routine repository owns routine persistence decisions.

## Phase 3: Experiments

**Purpose:** Move experiment definitions, exposure policy, target metrics, and
analysis contracts into the experiments slice after routine boundaries are stable.

**Files:**

- Create: `backend/app/domains/experiments/contracts.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/domains/experiments/**/*.py`
- Modify: `backend/app/domains/assistant/application/retrieval.py`
- Modify: `backend/app/domains/assistant/application/entity_resolution.py`
- Modify: `backend/app/domains/experiments/infra/sqlite_repository.py`
- Modify: `backend/app/infra/database.py`
- Test: `backend/tests/domains/experiments/*.py`
- Test: `backend/tests/domains/assistant/test_assistant_retrieval.py`
- Test: `backend/tests/domains/assistant/test_assistant_entity_resolution.py`

**Steps:**

- [ ] Move experiment contracts to `domains/experiments/contracts.py`.
- [ ] Keep pure math in `analysis_math.py`; do not move it to shared unless a
      second domain uses the exact same calculation.
- [ ] Move experiment SQLite functions behind `SqliteExperimentRepository`.
- [ ] Update assistant reads to depend on experiment application-facing types or
      read ports, not experiment internals.
- [ ] Shrink `app.models` and `app.infra.database` allowlists.
- [ ] Regenerate API types if schema output changes.
- [ ] Run backend lint, pyright, and tests.
- [ ] Run frontend check if API types changed.
- [ ] Commit with `refactor: tighten experiment ownership`.

**Exit criteria:**

- Experiment analysis and exposure policy are owned by experiments.
- Assistant no longer imports experiment internals except explicitly allowlisted
  evidence/read interfaces.

## Phase 4: Assistant After Analytics And Experiments

**Purpose:** Clean assistant dependencies after its evidence sources have stable
analytics and experiment boundaries.

**Files:**

- Create or modify: `backend/app/domains/assistant/application/contracts.py`
- Modify: `backend/app/domains/assistant/**/*.py`
- Modify: `backend/app/domains/assistant/infra/sqlite_repository.py`
- Modify: `backend/app/infra/database.py`
- Test: `backend/tests/domains/assistant/*.py`

**Steps:**

- [ ] Move assistant thread/message/run API contracts and persisted records out of
      `app.models` when touched.
- [ ] Keep runtime-specific types in `assistant/application/types.py`.
- [ ] Move assistant SQLite functions behind `SqliteAssistantRepository`.
- [ ] Replace direct experiment/analytics imports with evidence/read ports where
      previous phases created them.
- [ ] Shrink cross-slice and shared-bucket allowlists.
- [ ] Run backend lint, pyright, and tests.
- [ ] Regenerate API types and run frontend check if route schemas change.
- [ ] Commit with `refactor: tighten assistant ownership`.

**Exit criteria:**

- Assistant owns conversation/runtime persistence.
- Assistant reads analytics and experiments through stable evidence interfaces.

## Phase 5: Artifacts

**Purpose:** Separate artifact staging/bundle contracts from live routine runtime
contracts.

**Files:**

- Create: `backend/app/domains/artifacts/contracts.py`
- Modify: `backend/app/domains/artifacts/**/*.py`
- Modify: `backend/app/domains/routines/**/*.py`
- Modify: `backend/app/domains/artifacts/infra/sqlite_repository.py`
- Modify: `backend/app/infra/database.py`
- Test: `backend/tests/domains/artifacts/*.py`
- Test: `backend/tests/domains/routines/*.py`

**Steps:**

- [ ] Move assistant artifact, bundle, card-template draft, and capability request
      contracts to artifacts.
- [ ] Keep live routine schedule/card-log contracts in routines.
- [ ] Preserve the explicit artifacts-to-routines activation boundary.
- [ ] Move artifact SQLite functions behind `SqliteArtifactRepository`.
- [ ] Shrink shared-bucket allowlists.
- [ ] Run backend lint, pyright, and tests.
- [ ] Regenerate API types and run frontend check if route schemas change.
- [ ] Commit with `refactor: tighten artifact ownership`.

**Exit criteria:**

- Artifacts owns staged/generated content.
- Routines owns live execution state.

## Phase 6: Programs After Routines And Experiments

**Purpose:** Clean program spec persistence after the domains it will eventually
activate are stable.

**Files:**

- Create: `backend/app/domains/programs/contracts.py`
- Modify: `backend/app/domains/programs/**/*.py`
- Modify: `backend/app/domains/programs/infra/sqlite_repository.py`
- Modify: `backend/app/infra/database.py`
- Test: `backend/tests/domains/programs/test_programs_service.py`

**Steps:**

- [ ] Move program and program-version contracts to programs.
- [ ] Keep program import as spec/version persistence only; do not implement
      routine or experiment activation in this cleanup.
- [ ] Move program SQLite functions behind `SqliteProgramRepository`.
- [ ] Shrink shared-bucket allowlists.
- [ ] Run backend lint, pyright, and tests.
- [ ] Regenerate API types and run frontend check if route schemas change.
- [ ] Commit with `refactor: tighten program ownership`.

**Exit criteria:**

- Programs owns its contracts and persistence.
- No new coupling to routines or experiments is introduced.

## Opportunistic Small Slices

Journal and profile can be done when touched by feature work or when a small
cleanup slot is useful:

- `domains/journal/contracts.py`: `DailyCheckIn`, `DailyCheckInsResponse`, `Note`,
  `NotesResponse`.
- `core/profile/contracts.py`: `DEFAULT_PROFILE_ID`, `UserProfile`, `Goal`,
  `GoalsResponse` if goals remain profile-owned.

These are safe early extractions, but they should not interrupt the analytics →
routines → experiments → assistant dependency path.

## Validation Rules For Every Phase

Run these for backend-only phases:

```bash
cd backend && uv run ruff check app/ tests/
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

If any backend route contract changes, also run:

```bash
bash scripts/generate-api-types.sh
cd frontend && npm run check
```

If parser, watcher, ingest, archive extraction, startup ingest, cache invalidation,
or data-root resolution changes, also run the real local smoke check required by
AGENTS.md against the actual data tree.

## Completion Signals

The roadmap is complete when:

- `app.models` contains only genuinely shared base classes or is eliminated.
- `app.stats` contains only domain-neutral numeric primitives or is eliminated.
- `app.infra.database` no longer exposes domain-specific repository functions to
  application modules.
- Architecture allowlists are smaller than at the start of each phase.
- API type generation remains stable except for intentional ownership-driven
  import/order changes.
