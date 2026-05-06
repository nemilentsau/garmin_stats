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

### Main flow

There are two major paths:

- Ingest path: FIT files -> `parser.py` -> `stats.py` -> SQLite
- Read path: SQLite -> repository adapters -> domain/core application slices or legacy services -> JSON API -> frontend

### Core modules

- `backend/app/models.py`
  Pydantic contracts for Garmin metrics, assistant state, routine runtime, and API responses.

- `backend/app/bootstrap/`
  App factory, lifespan wiring, router registration, and the current composition root.

- `backend/app/core/`
  Shared cross-cutting modules being extracted out of the flat app root.

- `backend/app/parser.py`
  FIT parsing and timestamp normalization into local time.

- `backend/app/stats.py`
  Deterministic aggregations and response shaping.

- `backend/app/main.py`
  Compatibility entrypoint that exposes the assembled FastAPI app.

### Infrastructure

- `backend/app/infra/database.py`
  SQLite schema, read/write helpers, data-root config, and ingest bookkeeping.

- `backend/app/infra/cache.py`
  In-memory cache with generation-based invalidation.

- `backend/app/infra/events.py`
  SSE event bus.

- `backend/app/infra/watcher.py`
  Data-directory watcher and heartbeat loop.

### Active service areas

- `domains/assistant/`
  Assistant domain slice. `api/threads.py` owns `/api/assistant` endpoints, `application/` owns retrieval-first chat and thread use-cases, and `infra/` owns SQLite repository + Claude runtime adapters.

- `domains/routines/`
  The first migrated domain slice. `api/` owns mounted routes, `application/` owns use cases for catalog, activation, schedule, and today, and `infra/` owns the SQLite repository adapter.

- `domains/garmin_analytics/`
  Garmin-derived analytical read models and dashboard use cases. This domain owns dashboard overview, daily aggregates, period summaries, raw biometric routes for wellness, sleep, HRV, and skin temperature, plus the current recovery insight/analysis implementations for heart rate, HRV, sleep, stress, and body battery. Activity/session marts are reserved here for future runs, meditations, and strength sessions.

- `domains/experiments/`
  Experiment CRUD, design preview/import, target metric registry, exposure
  derivation, and N=1 analysis. This domain owns `/api/experiments` and
  `/api/target-metrics`. Experiment analysis is a cached read model that
  refreshes after exposure changes and on stale date-sensitive reads. `api/`
  owns FastAPI routes, `application/` owns named use cases (`management`,
  `preview`, `exposures`, `exposure_sync`, `analysis_cache`, `analysis`, and
  `target_metrics`) plus repository ports, and `infra/` owns the SQLite
  repository adapter. It has no separate `domain/` package until experiment
  rules need a dedicated pure domain model layer.

- `domains/artifacts/`
  Assistant-authored artifact staging and publishing. This domain owns
  `/api/cards`, `/api/assistant/artifacts`, and
  `/api/assistant/artifact-bundles`. It validates/imports card and routine
  artifacts, tracks bundle revisions and capability requests, persists
  artifact/card data through its SQLite repository adapter, and delegates live
  routine activation writes to `domains/routines`.

- `domains/journal/`
  Subjective/user-authored context. This domain owns `/api/checkins` and `/api/notes`, including daily check-ins, freeform notes, and future journal-style context that can ground assistant coaching and experiment interpretation. `api/` owns FastAPI routes, `application/` owns use cases and repository ports, and `infra/` owns the SQLite repository adapter.

- `core/profile/`
  App-level profile configuration. This owns `/api/profile` without treating profile as a product domain. The route uses the composition-root repository, `application.py` owns profile use cases, `ports.py` defines the storage contract, and `infra/` owns the SQLite adapter.

- `domains/programs/`
  Secondary backend domain for program spec import and management. This domain
  owns `/api/programs`; `api/` owns FastAPI routes, `application/` owns import,
  activation/retirement, and version use cases plus repository ports, and
  `infra/` owns the SQLite repository adapter. Program imports currently persist
  the program spec and version history only; protocol, routine, and experiment
  activation is intentionally not implemented yet.

### Migrated slice boundary convention

The project now uses "migrated" to mean both route/file-layout migration and
strict boundary migration.

- `api/` modules may import FastAPI and `build_container()`, then pass container-owned dependencies into application use cases.
- `application/` modules must stay FastAPI-free, must not call `build_container()`, and must not import `app.infra.database`, `app.services.*`, or `app.routers.*`.
- `infra/` modules are the SQLite boundary for migrated slices and may wrap `app.infra.database`.
- Transitional slices must be called out in architecture tests and docs with their allowed boundary violations.
- Architecture tests guard migrated shim removal and prevent new imports of removed flat `app.routers.*` or `app.services.*` paths.

Fully migrated slices today: `domains/assistant`, `domains/routines`,
`domains/garmin_analytics`, `domains/experiments`, `domains/artifacts`,
`domains/programs`, `domains/journal`, and `core/profile`.
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
- `/api/days`
- `/api/wellness`
- `/api/sleep`
- `/api/daily-aggregates`
- `/api/skin-temp`
- `/api/heart-rate`
- `/api/hrv`
- `/api/stress`
- `/api/body-battery`
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

- Domain routes now mount from `backend/app/domains/routines/api/`.
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

- `domains/artifacts/api/` owns artifact, bundle, and card-template routes.
- `domains/artifacts/application/` owns validation, bundle preview/import, capability requests, and activation orchestration.
- `domains/artifacts/infra/` owns the artifact/card SQLite repository adapter.
- Activated cards/routines become live runtime data owned by `domains/routines`.
- Future experiment/program artifacts should enter through this domain, then delegate final writes to `domains/experiments` or `domains/programs`.

Normal artifact flow:

`assistant/generated JSON -> artifact draft -> validated artifact -> imported bundle -> activation -> live domain record`

## Garmin Analytics Boundary

Garmin analytics is biometric-first but not `DailyMetric`-only.

- Domain routes now mount from `backend/app/domains/garmin_analytics/api/` for dashboard overview, wellness, sleep, HRV, skin temperature, daily aggregates, heart-rate insights/analysis/distribution, stress analysis, and body-battery analysis.
- Migrated Garmin analytics flat route and service shims have been removed; new code should import from `backend/app/domains/garmin_analytics/`.
- `/api/days` stays outside this domain because it describes ingested file availability and parser summaries.
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
