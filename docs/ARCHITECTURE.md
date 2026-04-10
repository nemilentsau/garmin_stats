# Architecture

This file is a current-state code map. It is not a roadmap and it is not a historical implementation diary.

## Product Shape

The shipped app has three active product centers:

1. Recovery dashboard and metric drill-downs
2. Assistant chat with stored runs and snapshots
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
- Read path: SQLite -> domain application or legacy services -> JSON API -> frontend

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

- `assistant.py`, `assistant_context.py`, `assistant_runtime.py`
  Assistant orchestration and prompt/runtime integration.

- `domains/routines/`
  The first migrated domain slice. `api/` owns mounted routes, `application/` owns use cases for catalog, activation, schedule, and today, and `infra/` owns the SQLite repository adapter.

- `dashboard.py`
  Recovery dashboard summaries.

- `heart_rate.py`, `heart_rate_analysis.py`
- `hrv.py`, `hrv_analysis.py`
- `sleep_analysis.py`
- `stress_analysis.py`
- `body_battery_analysis.py`
  Metric-specific analysis and drill-down logic.

- `training_specs.py`
  Assistant artifact validation/import/activation. Routine activation now delegates to `domains/routines/application/activation.py`.

- `schedule_projection.py`
  Compatibility wrapper over `domains/routines/application/schedule_window.py`.

- `today.py`
  Compatibility wrapper over `domains/routines/application/today.py`.

- `profile.py`, `checkins.py`, `notes.py`, `experiments.py`, `programs.py`, `target_metrics.py`
  Secondary/parked domain services still present in the backend.

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
