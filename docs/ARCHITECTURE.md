# Architecture

This file is a current-state code map. It is not a roadmap and it is not a historical implementation diary.

## Product Shape

The shipped app has three active product centers:

1. Recovery dashboard and metric drill-downs
2. Assistant chat with retrieval-first evidence bundles and stored runs
3. Routine runtime shared by Creation, Schedule, and Today

Experiments remain backend-supported and domain-owned, but the frontend experiment screens are intentionally parked. Programs remain a secondary backend area.

## Project Layout

- `backend/app/`
  FastAPI application code.

- `backend/tests/`
  Backend tests organized by ownership: architecture guards, bootstrap, infra,
  core, and domain slices.

- `frontend/src/`
  SvelteKit application.

- `storage/`
  Local SQLite database, created at runtime.

- `data/garmin_health_stats/`
  Garmin day archives and extracted FIT files.

## Backend

Boundary tests guard module intent, not a mandatory folder template. Larger
slices may use `api/`, `application/`, and `infra/` packages when those layers
contain multiple stable concepts. Small capability slices should stay flatter
when subpackages would only hold one file.

### Main flow

There are two major paths:

- Ingest path: FIT files -> `parser.py` -> Garmin health daily metric composer -> SQLite
- Read path: SQLite -> repository adapters -> domain/core application slices -> JSON API -> frontend

The Garmin health dependency direction is:

- `parser.py` and `garmin_sync` ingest adapters -> `garmin_health`, `app.utils`
- `garmin_analytics` -> `garmin_health`, `app.utils`
- `experiments` and `assistant` -> `garmin_health` contracts, and analytics
  adapters only when loading analytics read data
- `garmin_health` -> `app.contracts.base`, `app.utils`
- `app.utils` -> stdlib and numpy only

### Core modules

- `backend/app/contracts/base.py`
  Shared Pydantic response-base helpers. User-facing contracts live with their
  owning slices, for example `domains/routines/contracts.py`,
  `domains/experiments/contracts.py`, and `core/profile/contracts.py`. Tiny
  route-only response models may live directly with their route module.

- `backend/app/bootstrap/`
  App factory, router registration, lifespan entrypoint, process-runtime task
  wiring, and the current composition root. Cross-domain reactions such as
  "refresh experiment analyses after Garmin ingest" belong here rather than in
  the Garmin sync or experiment slices.

- `backend/app/core/`
  Shared cross-cutting modules being extracted out of the flat app root.

- `backend/app/parser.py`
  FIT parsing and timestamp normalization into local time.

- `backend/app/utils/`
  Shared, domain-agnostic helpers. See "Shared Utilities" below for the rule on what may live here.

- `backend/app/domains/garmin_health/`
  Canonical Garmin health contracts and deterministic daily metric composition
  used by parser, ingest persistence, analytics, experiments, and assistant.

- `backend/app/main.py`
  Compatibility entrypoint that exposes the assembled FastAPI app.

### Shared Utilities (`app/utils/`)

`app/utils/` is the only place above the domain layer where general-purpose helpers may live. It exists so two or more domains can share a primitive operation without one domain importing from another.

A helper belongs in `app/utils/` only when **all three** rules hold:

1. **Primitive-only signatures.** Inputs and outputs are language types (numbers, strings, datetimes, sequences, mappings) — never domain models like `DayData`, `DailyMetric`, `RoutineCard`, or `ExperimentExposure`.
2. **No domain vocabulary in names.** Function and type names use generic terms (`safe_avg`, `percentile_rank`, `ScalarSummary`, `now_utc`). Names like `normalize_hrv_status`, `compute_hr_zones`, `classify_recovery` are domain-bound even when small, and stay in their owning domain.
3. **Two or more consumers already need it.** Don't promote on speculation. A helper used by exactly one domain stays in that domain. Promote on the second real consumer, in the same PR that introduces it.

Counter-examples (these belong in a domain, not `app/utils/`):
- `compute_daily_heart_rate(wellness: DayWellness)` — takes a domain type. → `garmin_health/domain/daily_metrics/`.
- `prior_7d_avg(...)` — encodes a period-window concept specific to analytics. → `garmin_analytics/domain/primitives/trends.py`.
- `format_routine_card_label(card)` — single consumer + domain type. → `routines/`.

Forbidden in `app/utils/`:
- Imports from `app.domains.*`, `app.infra.*`, `app.routers.*`, or `app.bootstrap.*`. Allowed dependencies are stdlib and numpy.
- Functions whose name or signature names a Garmin metric, routine concept, experiment concept, assistant concept, or persistence detail.
- Re-exports from a domain (use the domain directly).

Adding a helper here is a deliberate promotion, not a default landing spot. When in doubt, keep it domain-local — promotion is cheap to do later, demotion is not.

Current contents:
- `app/utils/timeutil.py` — UTC clock helpers.
- `app/utils/numeric.py` — null-tolerant scalar summary, histogram, and percentile helpers used by `garmin_health` daily-metric calculators and `garmin_analytics` dashboard / insights / analysis modules.

### Infrastructure

- `backend/app/infra/database.py`
  SQLite schema, shared read/write helpers, data-root config, and ingest metadata table.

- `backend/app/infra/cache.py`
  In-memory cache with generation-based invalidation.

- `backend/app/realtime/events.py`
  SSE event bus and heartbeat loop.

- `backend/app/realtime/routes.py`
  Realtime transport endpoint for `/api/events`.

### Active service areas

- `domains/assistant/`
  Assistant chat and retrieval-first evidence context. This slice uses a flat
  small-capability layout: `routes.py` owns `/api/assistant` HTTP and streaming
  endpoints, `application/` owns thread catalog, intent classification, entity
  resolution, read-model interaction, evidence assembly, retrieval, and chat
  orchestration, `domain/` owns pure assistant evidence payload policy,
  `dependencies.py` owns conversation/read-model/runtime dependencies,
  `adapters.py` owns assistant SQLite persistence and explicit read-model
  wiring, `runtime.py` owns Claude Code subprocess execution, and `contracts.py`
  owns assistant API and persistence shapes.

- `domains/routines/`
  Routine catalog, schedule projection, activation, and Today execution. This
  slice uses a flat small-capability layout: `routes.py` owns `/api/routines`
  and `/api/today`, `application/` owns use cases for catalog, activation,
  schedule, and today, `schedule.py` owns pure schedule helpers,
  `dependencies.py` owns repository/observer/callable dependencies,
  `adapters.py` owns the SQLite repository adapter, and `contracts.py` owns
  routine API/persistence/activation command shapes.

- `domains/garmin_sync/`
  Garmin ingest and Garmin Connect download orchestration. This domain owns
  `/api/ingest`, `/api/ingest/status`, and `/api/ingest/sync`. It uses a
  small-capability layout with domain policy at the package root and concrete
  adapters under `infra/`: `routes.py` owns FastAPI routes, `workflows.py` owns
  ingest/status/sync orchestration, `dependencies.py` owns workflow ports and
  callables, `infra/sqlite_ingest.py` owns SQLite ingest/status writes,
  `infra/filesystem.py` owns archive extraction and FIT source fingerprinting,
  `infra/watcher.py` owns one stateful Garmin data-directory watcher instance
  and suspend/resume controls, `infra/runtime.py` owns startup archive
  reconciliation through injected Garmin sync dependencies,
  `infra/garmin_connect.py` owns Garmin Connect login/download details,
  `infra/factory.py` wires the production dependency bundle, and `contracts.py`
  owns ingest/sync API response models.

- `domains/garmin_health/`
  Canonical Garmin health data slice. This domain owns parsed reading containers,
  persisted `DailyMetric` rows, nullable daily metric stat contracts,
  Garmin-vocabulary daily metric calculators, and pure day-to-metric
  composition. It has no routes, repositories, sync workflows, dashboard reads,
  experiment analysis, or assistant retrieval logic.

- `domains/garmin_analytics/`
  Garmin-derived analytical read models and dashboard use cases. This domain owns dashboard overview, daily metric response wrapping, period summaries, metric-specific raw biometric routes, sleep, HRV, and skin temperature reads, plus the current metric analysis and selected-day insight implementations for heart rate, HRV, sleep, stress, and body battery. `routes.py` owns HTTP only, `application/` owns named read use cases, `domain/` owns read-model calculations and response shaping, `adapters.py` owns persistence wiring, and `contracts/` owns API/read-model contracts split by concern (`raw`, `period`, `analysis`, `insights`, and `dashboard`). Activity/session marts are reserved here for future runs, meditations, and strength sessions.

- `domains/experiments/`
  Experiment CRUD, design preview/import, target metric registry, exposure
  derivation, and N=1 analysis. This domain owns `/api/experiments` and
  `/api/target-metrics`. Experiment analysis is a cached read model that
  refreshes after exposure changes and on stale date-sensitive reads. It uses a
  flat route/adapter/dependency layout: `routes.py` owns experiment and target
  metric HTTP routes, `application/` owns named use cases (`management`,
  `preview`, `exposures`, `exposure_sync`, `analysis_cache`, `analysis`, and
  `target_metrics`), `dependencies.py` owns repository ports, `domain/` owns
  pure experiment analysis, experiment-local statistical primitives, metric path
  resolution, and exposure scoring, and `adapters.py` owns the SQLite repository
  adapter.

- `domains/artifacts/`
  Assistant-authored artifact staging and publishing. This domain owns
  `/api/cards`, `/api/assistant/artifacts`, and
  `/api/assistant/artifact-bundles`. It uses a flat small-capability layout:
  `routes.py` owns HTTP routes, `application/` owns staging, bundle planning,
  activation, validation, and card catalog use cases, `dependencies.py` owns
  repository dependencies, `adapters.py` owns SQLite persistence wiring, and
  `contracts.py` owns staged artifact and bundle API shapes. Artifacts delegates
  live routine activation writes to `domains/routines`.

- `domains/journal/`
  Subjective/user-authored context. This domain owns `/api/checkins` and
  `/api/notes`, including daily check-ins, freeform notes, and future
  journal-style context that can ground assistant coaching and experiment
  interpretation. `routes.py` owns HTTP routes, `application/` owns check-in
  and note use cases, `dependencies.py` owns the journal repository dependency
  protocol, and `adapters.py` owns SQLite journal persistence and recent
  check-in caching.

- `core/profile/`
  App-level profile configuration. This owns `/api/profile` without treating profile as a product domain. The route uses the composition-root repository, `application.py` owns profile use cases, `ports.py` defines the storage contract, and `infra/` owns the SQLite adapter.

- `domains/programs/`
  Secondary backend domain for program spec import and management. This domain
  owns `/api/programs`; `routes.py` owns HTTP routes, `application/` owns import,
  activation/retirement, and version use cases, `dependencies.py` owns the
  repository dependency protocol, and `adapters.py` owns SQLite program spec and
  version-history persistence. Program imports currently persist the program
  spec and version history only; protocol, routine, and experiment activation is
  intentionally not implemented yet.

### Module Ownership Charters

These charters are the boundary source of truth. A module can be a product domain,
an operational capability, or an analytical read model; the package name alone is
not proof that the design is sound.

#### `assistant`

- Owns: assistant threads, messages, evidence bundle assembly, retrieval routing,
  assistant memory records, assistant plan/context/evidence-card persistence,
  and runtime interaction.
- Does not own: Garmin parsing, Garmin ingest, routine scheduling writes,
  experiment exposure derivation, or artifact activation.
- May import: its own contracts, application helpers, and dependencies, plus explicitly
  allowlisted read dependencies needed to build evidence context, including
  canonical Garmin health contracts.
- Must not import: Garmin sync, Garmin analytics application internals, routine
  activation internals, FastAPI from application modules, or SQLite helpers from
  application modules.
- Public entrypoints: `/api/assistant` routes and assistant application use cases
  called by those routes.

#### `routines`

- Owns: routine catalog reads, routine activation, assignment projection, Today
  card presentation, and Today log writes.
- Does not own: assistant artifact staging, experiment analysis, program import,
  Garmin ingest, or Garmin analytics.
- May import: its own pure schedule helpers, routine dependencies, and
  routine-owned contracts.
- Must not import: artifacts, experiments, assistant, Garmin sync, Garmin
  analytics, FastAPI from application modules, or SQLite helpers from application
  modules.
- Public entrypoints: `/api/routines`, `/api/today`, schedule-window use cases,
  and Today log use cases.

#### `garmin_sync`

- Owns: Garmin archive acquisition, ingest status, manual ingest orchestration,
  Garmin Connect wellness archive download orchestration, watcher suspension
  during sync, and affected-date ingest decisions.
- Does not own: FIT parsing semantics, analytics calculations, dashboard reads,
  experiment refresh policy, routine scheduling, assistant evidence, or frontend
  presentation.
- May import: its own workflow ports, private workflow/runtime helpers, owned
  ingest/sync contracts, SQLite connection primitives, cache invalidation,
  event bus publishing, canonical Garmin health composition, and adapter code
  under `domains/garmin_sync/infra` for archive extraction, watcher control,
  filesystem writes, clock, SQLite ingest, and Garmin Connect login/download
  details.
- Must not import: routines, experiments, assistant, artifacts, journal,
  programs, Garmin analytics application modules, FastAPI from application
  modules, or SQLite helpers from application modules.
- Public entrypoints: `/api/ingest`, `/api/ingest/status`, `/api/ingest/sync`,
  `trigger_ingest`, `get_ingest_status`, and `sync_garmin`.

`garmin_sync` is a data acquisition capability, not a business domain. It is core
to the product because the app depends on current local Garmin data, but `core/`
is reserved for shared app primitives rather than important product workflows.

#### `garmin_health`

- Owns: canonical parsed Garmin reading rows, day-level containers, persisted
  daily metric contracts, Garmin-vocabulary daily metric calculators, and pure
  raw-day-to-daily-metric composition.
- Does not own: archive acquisition, watcher/startup ingest orchestration,
  SQLite persistence, dashboard reads, period summaries, experiment analysis,
  assistant retrieval, frontend presentation, or API routing.
- May import: `app.contracts.base`, `app.utils`, and its own contracts/domain
  modules.
- Must not import: Garmin sync, Garmin analytics, experiments, assistant,
  routines, artifacts, journal, programs, infrastructure adapters, FastAPI from
  application modules, or SQLite helpers from application modules.
- Public entrypoints: canonical contracts under
  `app.domains.garmin_health.contracts`, daily metric composition under
  `app.domains.garmin_health.domain.daily`, and daily metric calculators under
  `app.domains.garmin_health.domain.daily_metrics`.

#### `garmin_analytics`

- Owns: Garmin-derived read models, biometric API reads, dashboard overview,
  daily metric API response wrapping, period summaries, metric drill-down
  insights, and recovery analysis responses.
- Does not own: archive acquisition, parser timestamp normalization, routine
  execution, canonical daily metric composition, experiment exposure derivation,
  assistant runtime behavior, or subjective journal writes.
- May import: its biometric repository dependency protocol, Garmin analytics
  domain helpers, Garmin analytics contracts, canonical Garmin health
  contracts/calculators, and domain-agnostic helpers from `app.utils`.
- Must not import: Garmin sync, routines, experiments, assistant, artifacts,
  journal, programs, FastAPI from application modules, or SQLite helpers from
  application modules.
- Public entrypoints: dashboard, sleep, HRV, skin temperature, daily metric,
  heart-rate, stress, body-battery, respiration, and pulse-ox API routes. Application files
  are named by concern: `raw_biometrics.py` reads raw biometric tables,
  `daily_aggregates.py` wraps persisted daily metrics and computes period windows,
  `dashboard.py` loads overview inputs,
  `metric_analysis.py` loads cached chart/trend analysis read models, and
  `metric_insights.py` loads selected-day insight read models.

#### `experiments`

- Owns: experiment definitions, design preview/import, target metric registry,
  experiment-day exposures, cached N=1 analysis, and active-analysis refresh.
- Does not own: Today log storage, routine schedule projection internals beyond
  explicit routine dependencies/use cases, Garmin ingest, assistant runtime, or artifact
  staging.
- May import: experiment repository dependencies, experiment-owned contracts,
  allowlisted routine read/projection contracts needed for exposure derivation,
  canonical Garmin health contracts, and experiment-owned domain analysis
  helpers.
- Must not import: Garmin sync, Garmin analytics application internals except
  through analytics read adapters, assistant runtime, artifact persistence
  internals, FastAPI from application modules, or SQLite helpers from application
  modules.
- Public entrypoints: `/api/experiments`, `/api/target-metrics`, experiment
  management use cases, exposure use cases, and analysis refresh/read use cases.

#### `artifacts`

- Owns: assistant-authored artifact staging, card template persistence before
  activation, bundle preview/import, bundle revision tracking, and capability
  request records.
- Does not own: live routine schedule semantics after activation, experiment
  protocol semantics, program lifecycle semantics, assistant chat runtime, or
  Garmin data.
- May import: artifact repository dependencies, artifact-owned contracts, and
  allowlisted routine activation contracts/dependencies for publishing live
  cards/routines.
- Must not import: Garmin sync, Garmin analytics, journal, programs,
  experiments application internals, assistant runtime internals, FastAPI from
  application modules, or SQLite helpers from application modules.
- Public entrypoints: `/api/cards`, `/api/assistant/artifacts`,
  `/api/assistant/artifact-bundles`, bundle preview, and bundle import.

#### `journal`

- Owns: user-authored daily check-ins, freeform notes, and journal context that
  can later be read by assistant or experiment interpretation.
- Does not own: Garmin metrics, routine execution, experiment definitions,
  assistant runtime, or analytics computations.
- May import: journal repository dependencies and journal-owned contracts.
- Must not import: Garmin sync, Garmin analytics, routines, experiments,
  assistant, artifacts, programs, FastAPI from application modules, or SQLite
  helpers from application modules.
- Public entrypoints: `/api/checkins`, `/api/notes`, check-in use cases, and
  note use cases.

#### `programs`

- Owns: imported program specs, program lifecycle status, and program version
  history.
- Does not own: protocol activation, routine activation, experiment creation,
  artifact staging, Garmin data, or assistant runtime behavior.
- May import: program repository ports and program-owned contracts.
- Must not import: Garmin sync, Garmin analytics, assistant, artifacts, journal,
  routine activation internals, experiment management internals, FastAPI from
  application modules, or SQLite helpers from application modules.
- Public entrypoints: `/api/programs` and program import/list/read use cases.

#### `core/profile`

- Owns: app-level user profile configuration and profile persistence contracts.
- Does not own: Garmin data, routine runtime, experiments, assistant behavior,
  artifacts, journal content, programs, or analytics.
- May import: profile repository ports and profile-owned contracts.
- Must not import: any `app.domains.*` package, FastAPI from application modules,
  or unrelated SQLite helpers from application modules.
- Public entrypoints: `/api/profile` and profile read/write use cases.

### Migrated slice boundary convention

The project now uses "migrated" to mean both route/file-layout migration and
strict boundary migration.

- Route modules may import FastAPI and `build_container()`, then pass container-owned dependencies into application use cases.
- `application/` modules must stay FastAPI-free, must not call `build_container()`, and must not import `app.infra.database`, `app.services.*`, or `app.routers.*`.
- `adapters.py` modules are the SQLite or external-system boundary for flat migrated slices; they should own slice-specific persistence instead of wrapping `app.infra.database`.
- Transitional slices must be called out in architecture tests and docs with their allowed boundary violations.
- Architecture tests guard migrated shim removal and prevent new imports of removed flat `app.routers.*` or `app.services.*` paths.

Fully migrated slices today: `domains/assistant`, `domains/routines`,
`domains/garmin_sync`, `domains/garmin_analytics`, `domains/experiments`,
`domains/artifacts`, `domains/programs`, `domains/journal`, and `core/profile`.
Transitional domain-routed slices today: none.

## Experiment Semantics

Experiment adherence is protocol-defined and day-grain.

- One `ExperimentExposure` represents one experiment-day for one `experiment_id + date`.
- Exposure is derived from whether the planned intervention dose for that day was satisfied, not from any single card in isolation.
- A routine may schedule multiple intervention cards on the same day. That is expected when the protocol requires multiple sessions or components.
- Do not collapse an experiment day to a "best card status" and do not treat multiple same-day linked cards as ambiguity. The correct question is whether the prescribed daily dose was met, partially met, missed, or is still unresolved.
- Experiment analysis is not a permanent historical snapshot for active windows. It is recomputed after exposure changes and refreshed on read when its `analysis_date` is stale.

## Backend Route Inventory

### Health and ingest

- `/api/ingest`
- `/api/dashboard`
- `/api/sleep`
- `/api/daily-aggregates`
- `/api/skin-temp`
- `/api/heart-rate`
- `/api/hrv`
- `/api/stress`
- `/api/body-battery`
- `/api/respiration`
- `/api/pulse-ox`
- `/api/events`

### Assistant

- `/api/assistant`
- `/api/assistant/artifacts`
- `/api/assistant/artifact-bundles`

### Routine runtime

- `/api/cards`
- `/api/routines`
- `/api/today`

### Journal

- `/api/checkins`
- `/api/notes`

### Experiments

- `/api/experiments`
- `/api/target-metrics`

### Core app config

- `/api/profile`

### Secondary backend domains

- `/api/programs`

## Routine Runtime Boundary

This is the most important current product boundary.

- Domain routes now mount from `backend/app/domains/routines/routes.py`.
- Flat routine/today router and service compatibility shims have been removed.
- `/routines/schedule` handles routine review and bundle import
- `/today` reads one day of live compiled occurrences and writes logs only

Normal bundle flow:

`bundle JSON -> preview -> import -> auto-activate -> live schedule/today`

Important rules:

- preview performs no writes
- bundle import persists artifacts and auto-activates them
- Today does not create schedule structure
- schedule exceptions are still read for backward compatibility, but Today does not author them

## Artifacts Boundary

Artifacts is the staging and publishing layer for assistant-authored objects.

- `domains/artifacts/routes.py` owns artifact, bundle, and card-template routes.
- `domains/artifacts/application/` owns validation, bundle preview/import, capability requests, bundle id revisioning, and activation orchestration.
- `domains/artifacts/adapters.py` owns the SQLite artifact repository adapter.
- `domains/artifacts/dependencies.py` owns the artifact repository port.
- Activated cards/routines become live runtime data owned by `domains/routines`.
- Future experiment/program artifacts should enter through this domain, then delegate final writes to `domains/experiments` or `domains/programs`.

Normal artifact flow:

`assistant/generated JSON -> staged artifact or bundle import -> validated artifact -> activation -> live domain record`

## Garmin Analytics Boundary

Garmin analytics is biometric-first but not `DailyMetric`-only.

- Domain routes now mount from `backend/app/domains/garmin_analytics/routes.py` for dashboard overview, sleep, HRV, skin temperature, daily metrics, heart-rate raw/insights/analysis/distribution, stress raw/analysis, body-battery raw/analysis, respiration raw, and pulse-ox raw.
- Migrated Garmin analytics flat route and service shims have been removed; new code should import from `backend/app/domains/garmin_analytics/`.
- `application/` is orchestration only: it loads repository data, handles route-level missing-data decisions, applies caching, and delegates calculations.
- `domain/aggregates/` owns deterministic period response shaping. Its composers stay thin: `garmin_health.domain.daily_metrics` owns metric-specific single-day rules, `period_metrics/` owns metric-specific period rules from raw readings, and period stats continue to come from raw readings rather than averaged daily summaries. `domain/analysis/` owns chart/trend analysis calculations, `domain/insights/` owns selected-day insight calculations, `domain/dashboard.py` owns dashboard readiness/vitals/sparkline/correlation calculations, and `domain/primitives/` owns generic numeric/window helpers.
- The legacy `/api/days` parser-summary route has been removed; route inventory
  now reflects user-facing analytics and ingest APIs only.
- Future activity/session data belongs in Garmin analytics as session-grain read models, not as forced fields on `DailyMetric`.

## Frontend

### Routes

- `/`
  Recovery dashboard overview.

- `/heart-rate`, `/hrv`, `/sleep`, `/stress`, `/body-battery`, `/respiration`, `/skin-temp`, `/pulse-ox`
  Metric detail routes.

- `/assistant`
  Assistant threads and chat.

- `/today`
  Execution board for one day.

- `/routines/schedule`
  Live 14-day schedule review and bundle import.

- `/experiments`, `/programs`
  Placeholder routes.

### Frontend conventions

- Svelte 5 runes
- typed API client in `frontend/src/lib/api.ts`
- generated API types in `frontend/src/lib/api-types.ts`
- display-only frontend for analytical values
- shared chart/color/format helpers in `frontend/src/lib/`

## Storage and Runtime Config

- Default DB path: `storage/garmin_stats.db`
- Default data path: `data/garmin_health_stats/`
- Environment overrides:
  - `GARMIN_DB_PATH`
  - `GARMIN_DATA_DIR`
  - `GARMINTOKENS`
  - `BACKEND_CORS_ORIGINS`
  - `PUBLIC_API_BASE_URL`

## Source Of Truth Docs

- [docs/README.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/README.md)
  Documentation index and source-of-truth guide.

- [README.md](/Users/andreinemilentsau/Projects/garmin_stats/README.md)
  Product overview, routes, setup, API map.

- [docs/DATA_SCHEMA_DESIGN.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/DATA_SCHEMA_DESIGN.md)
  Routine runtime design rules.

- [docs/ACTIVITY_ANALYTICS_DESIGN.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/ACTIVITY_ANALYTICS_DESIGN.md)
  Planned analytical foundation for activity sessions, derived daily training features, and experiment-day joins.

- [docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md)
  Bundle import contract.

- [FINDINGS.md](/Users/andreinemilentsau/Projects/garmin_stats/FINDINGS.md)
  Current dataset observations.
