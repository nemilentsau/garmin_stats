# Garmin Health Assistant

This repo is a local-first health assistant built on Garmin recovery data.

The product is currently recovery-first:

- the backend ingests Garmin FIT exports and computes deterministic health metrics
- the frontend renders dashboards, Today, schedule review, and assistant flows
- the assistant works from curated snapshots, not raw database access
- routines run through a structured bundle pipeline instead of ad hoc markdown imports

Experiments are the next product step, but the current foundation is the dashboard + assistant + routine runtime.

## Current Product

### Recovery dashboard

- overview and metric drill-downs for heart rate, HRV, sleep, stress, body battery, respiration, skin temperature, and pulse ox
- backend-owned statistics only; the frontend does not compute analytical values

### Assistant

- persistent assistant threads
- stored runs and context snapshots
- streamed responses backed by curated health context

### Routine runtime

- `/routines/schedule` is the routine surface
- `/today` is the execution surface

The intended split is:

- Schedule: inspect compiled live occurrences over the next 14 days and import bundles
- Today: log what actually happened for one day

Schedule is the only routine-management UI entry point.

### Parked surfaces

- `/experiments` is intentionally parked until it can sit on top of the current routine runtime cleanly
- `/programs` is intentionally parked for the same reason

## Routine Flow

The routine system accepts deterministic bundle JSON, not arbitrary markdown.

Canonical flow:

`source note -> bundle JSON -> preview -> import -> auto-activate -> schedule/today`

Important details:

- preview performs no writes
- bundle import persists artifacts and auto-activates them in dependency order
- low-level assistant artifacts still exist for debugging/manual flows, but they are not the normal user path
- Today only logs execution state; it does not author schedule structure
- Today card logs now auto-derive linked experiment exposure rows for routine-linked experiments, so adherence comes from the live routine runtime instead of a separate manual logging path

Bundle examples live in:

- [docs/morning_stretching_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/morning_stretching_bundle.json)
- [docs/two_week_core_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_core_bundle.json)
- [docs/two_week_meditation_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_meditation_bundle.json)

The bundle contract is documented in [docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md).

## Main Routes

- `/`
  Recovery dashboard overview.

- `/assistant`
  Persistent recovery assistant chat.

- `/today`
  One-day execution board built from live compiled routines and logs.

- `/routines/schedule`
  14-day live schedule review plus bundle import.

- `/routines`
  Redirects to `/routines/schedule`.

- `/experiments`
  Parked placeholder.

- `/programs`
  Parked placeholder.

## Running Locally

### Prerequisites

- Python `3.14`
- Node.js `20+`
- `uv`

### Backend

```bash
cd backend
uv sync --python 3.14
uv run uvicorn app.main:app --reload
```

Backend default: `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend default: `http://localhost:5173`

### Tests and validation

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd frontend && npm run check
```

### API type generation

If backend models or route schemas change:

```bash
bash scripts/generate-api-types.sh
```

### Re-ingest after parser changes

If `backend/app/parser.py` changes:

```bash
cd backend
uv run python ../scripts/reingest.py
```

## Data Layout

```text
data/
  garmin_health_stats/
    YYYY-MM-DD.zip
    YYYY-MM-DD/
      *_WELLNESS.fit
      *_SKIN_TEMP.fit
      *_METRICS.fit
      ...
```

The ingest pipeline handles both the day archives and the extracted day folders.

## Repo Map

- `backend/app/models.py`
  Pydantic contracts for Garmin data, assistant state, routines, and API responses.

- `backend/app/bootstrap/`
  FastAPI app assembly, lifespan wiring, router registration, and dependency container.

- `backend/app/domains/routines/`
  First migrated backend domain slice for routines catalog, schedule window, today, and activation.

- `backend/app/domains/garmin_analytics/`
  Migrated backend domain slice for Garmin-derived dashboard and biometric read models. The first slice owns dashboard overview, raw wellness/sleep/HRV/skin-temperature reads, daily aggregates, and windowed period summaries.

- `backend/app/parser.py`
  FIT parsing and local-time timestamp normalization.

- `backend/app/stats.py`
  Deterministic aggregate/stat computation.

- `backend/app/infra/`
  SQLite persistence, ingest bookkeeping, cache, SSE bus, watcher.

- `backend/app/services/`
  Remaining flat service modules plus compatibility wrappers during the backend migration.

- `backend/app/routers/`
  Remaining flat route modules plus compatibility wrappers during the backend migration.

- `frontend/src/routes/`
  SvelteKit routes for dashboard, assistant, Today, routines, and parked placeholders.

- `frontend/src/lib/`
  Typed API client, shared formatting, colors, charts, and frontend helpers.

- [docs/ARCHITECTURE.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/ARCHITECTURE.md)
  Current-state code map.

- [docs/DATA_SCHEMA_DESIGN.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/DATA_SCHEMA_DESIGN.md)
  Routine runtime design notes.

- [docs/ACTIVITY_ANALYTICS_DESIGN.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/ACTIVITY_ANALYTICS_DESIGN.md)
  Planned analytical foundation for activity sessions, activity-derived daily features, and experiment joins.

- [FINDINGS.md](/Users/andreinemilentsau/Projects/garmin_stats/FINDINGS.md)
  Current analytical observations from the live dataset.

## API Surface

### Health data

- `GET /api/dashboard`
- `GET /api/days`
- `GET /api/wellness`
- `GET /api/sleep`
- `GET /api/daily-aggregates`
- `GET /api/skin-temp`
- `GET /api/heart-rate`
- `GET /api/hrv`
- `GET /api/stress`
- `GET /api/body-battery`

### Assistant

- `GET /api/assistant/threads`
- `POST /api/assistant/threads`
- `GET /api/assistant/threads/{thread_id}`
- `GET /api/assistant/threads/{thread_id}/messages`
- `POST /api/assistant/threads/{thread_id}/messages`
- `GET /api/assistant/artifacts`
- `POST /api/assistant/artifacts`
- `POST /api/assistant/artifacts/{artifact_id}/activate`
- `POST /api/assistant/artifact-bundles/preview`
- `POST /api/assistant/artifact-bundles/import`

`POST /api/assistant/artifact-bundles/import` is the normal routine import endpoint. It persists the validated bundle artifacts and auto-activates them into live runtime records.

### Routine runtime

- `GET /api/cards`
- `GET /api/routines`
- `GET /api/routines/{routine_id}`
- `GET /api/routines/{routine_id}/assignments`
- `GET /api/routines/schedule-window?start_date=YYYY-MM-DD`
- `GET /api/today?date=YYYY-MM-DD`
- `PUT /api/today/{date}/cards/{occurrence_key}`

### Parked/manual domains still present in the backend

- `GET/PUT /api/profile`
- `GET/POST /api/checkins`
- `GET/POST /api/notes`
- `GET/POST /api/experiments`
- `GET /api/experiments/{experiment_id}`
- `GET /api/experiments/{experiment_id}/analysis`
- `GET/POST /api/experiments/{experiment_id}/exposures`
- `GET/POST /api/programs`
- `GET /api/target-metrics`

The backend carries these surfaces, but the main product flow currently prioritizes assistant + recovery + routines.

## Current Direction

The app is already useful as a personal recovery assistant. It is not yet a general training-performance coach.

The next meaningful product layer is experiments built on top of the current routine runtime, not another reset of the routine model.

## Privacy

The `data/` directory is gitignored. Raw Garmin exports and derived local storage should never be committed.

Assistant requests send a curated context bundle, not the entire local dataset.
