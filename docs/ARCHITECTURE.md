# Architecture

This file is a current-state code map. It is not a roadmap and it is not a historical implementation diary.

## Product Shape

The shipped app has three active product centers:

1. Recovery dashboard and metric drill-downs
2. Assistant chat with retrieval-first evidence bundles and stored runs
3. Routine runtime shared by Creation, Schedule, and Today

Experiments and programs are not removed from the backend, but they are intentionally parked in the frontend.

## Project Layout

- `backend/app/`
  FastAPI application code.

- `backend/tests/`
  Backend tests.

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
- Read path: SQLite -> domain application slices or legacy services -> JSON API -> frontend

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

- `training_specs.py`
  Assistant artifact validation/import/activation. Routine activation now delegates to `domains/routines/application/activation.py`.

- `schedule_projection.py`
  Compatibility wrapper over `domains/routines/application/schedule_window.py`.

- `today.py`
  Compatibility wrapper over `domains/routines/application/today.py`.

- `profile.py`, `checkins.py`, `notes.py`, `experiments.py`, `programs.py`, `target_metrics.py`
  Secondary/parked domain services still present in the backend.

## Experiment Semantics

Experiment adherence is protocol-defined and day-grain.

- One `ExperimentExposure` represents one experiment-day for one `experiment_id + date`.
- Exposure is derived from whether the planned intervention dose for that day was satisfied, not from any single card in isolation.
- A routine may schedule multiple intervention cards on the same day. That is expected when the protocol requires multiple sessions or components.
- Do not collapse an experiment day to a "best card status" and do not treat multiple same-day linked cards as ambiguity. The correct question is whether the prescribed daily dose was met, partially met, missed, or is still unresolved.

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

### Secondary or parked backend domains

- `/api/profile`
- `/api/checkins`
- `/api/notes`
- `/api/experiments`
- `/api/target-metrics`
- `/api/programs`

## Routine Runtime Boundary

This is the most important current product boundary.

- Domain routes now mount from `backend/app/domains/routines/api/`.
- `backend/app/routers/routines.py` and `backend/app/routers/today.py` remain import-compatible wrappers while callers migrate.
- `/routines/schedule` handles routine review and bundle import
- `/today` reads one day of live compiled occurrences and writes logs only

Normal bundle flow:

`bundle JSON -> preview -> import -> auto-activate -> live schedule/today`

Important rules:

- preview performs no writes
- bundle import persists artifacts and auto-activates them
- Today does not create schedule structure
- schedule exceptions are still read for backward compatibility, but Today does not author them

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
