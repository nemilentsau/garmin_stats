# Garmin Health Assistant

Garmin Health Assistant is a local-first personal health application built around
Garmin wellness exports. It ingests Garmin FIT files, turns them into deterministic
recovery metrics, and presents them through a Svelte dashboard, a routine execution
surface, and an assistant that answers from curated local context.

The project is recovery-first today. It is useful for understanding HRV, sleep,
resting heart rate, stress, body battery, and related day-to-day recovery signals.
It also has a structured routine runtime that can schedule interventions and log
what happened. Experiments are supported in the backend and are intended to sit on
top of that routine runtime, but the primary product flow is currently dashboard +
assistant + routines.

## What It Does

- Imports daily Garmin health archives from `data/garmin_health_stats/`.
- Parses FIT files into local-time records and stores derived data in SQLite.
- Computes all statistics in the backend, including daily aggregates, period
  summaries, moving averages, readiness signals, and metric insights.
- Renders a frontend recovery dashboard with metric drill-downs for HRV, sleep,
  heart rate, stress, body battery, respiration, skin temperature, and pulse ox.
- Provides an assistant chat that uses curated evidence bundles instead of direct
  raw database access.
- Supports routine bundles that compile into live schedules and a Today execution
  board.
- Derives experiment exposure rows from completed routine cards when experiments
  are linked to routine interventions.

Raw Garmin exports and the local SQLite database stay on the developer machine.
The `data/` and `storage/` directories are gitignored.

## How Data Flows

```text
Garmin day zip
  -> extracted FIT files
  -> backend/app/parser.py
  -> backend/app/stats.py
  -> SQLite storage
  -> backend domain/application services
  -> FastAPI JSON endpoints
  -> SvelteKit frontend
```

FIT timestamps are stored in UTC by Garmin. The parser reads the per-day UTC
offset from Garmin monitoring metadata and shifts timestamps to local time during
ingest. New timestamp fields should follow the same parser path.

The frontend is display-only for analytics. It can format values and render
charts, but statistical computation and derived health values belong in the
backend API.

## High-Level Architecture

The backend is a FastAPI app under `backend/app/`. Its current direction is a
domain-oriented structure:

- `bootstrap/` assembles the FastAPI app, registers routers, owns lifespan wiring,
  and provides the dependency container.
- `infra/` contains shared infrastructure: SQLite persistence, ingest bookkeeping,
  cache invalidation, server-sent events, and file watching.
- `domains/garmin_analytics/` owns Garmin-derived read models, dashboard data,
  biometric reads, and recovery insights.
- `domains/assistant/` owns assistant threads, retrieval, evidence bundles, memory,
  and runtime integration.
- `domains/routines/` owns routine catalog, schedule projection, Today execution,
  and routine activation.
- `domains/artifacts/` is a transitional domain-routed slice that validates and
  imports assistant-authored cards and routine bundles before activating them
  into live runtime data.
- `domains/experiments/` is a transitional domain-routed slice for experiment
  definitions, target metrics, exposure derivation, and N=1 analysis.
- `domains/journal/` owns daily check-ins and notes.
- `core/profile/` owns app-level profile configuration.

Fully migrated slices follow the same boundary convention: API modules handle
FastAPI and dependency lookup, application modules own use cases and repository
ports without importing SQLite helpers or the dependency container, and infra
adapters are the SQLite boundary. Transitional slices are explicitly allowlisted
in architecture tests until their application persistence dependencies are moved
behind ports/adapters.

The frontend is a SvelteKit app under `frontend/src/`. It renders the recovery
overview, metric detail pages, assistant chat, Today board, and routine schedule
review. Shared API helpers and generated API types live in `frontend/src/lib/`.

For the full current code map and route inventory, see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Routine Runtime

Routines are imported through deterministic bundle JSON, not freeform markdown.
The normal flow is:

```text
bundle JSON -> preview -> import -> auto-activate -> schedule and Today
```

Preview validates without writing. Import persists validated artifacts and
activates cards before routines, because routines depend on card templates. Today
logs execution for a date; it does not author schedule structure.

The bundle format is documented in
[docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md](docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md).
Example bundles live in `docs/*_bundle.json`.

## Repository Layout

```text
backend/
  app/          FastAPI app, domain slices, parser, stats, infrastructure
  tests/        Backend tests organized by architecture, infra, core, and domain
frontend/
  src/          SvelteKit routes, components, API client, chart helpers
scripts/        Local utility scripts for Garmin download, ingest, FIT inspection
docs/           Architecture notes, data model notes, bundle specs, examples
data/           Local Garmin exports, ignored by git
storage/        Local SQLite database, ignored by git
```

## Running Locally

Prerequisites:

- Python 3.14
- Node.js 20+
- `uv`

Backend:

```bash
cd backend
uv sync --python 3.14
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Default local URLs:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

## Data And Ingest

Expected Garmin data layout:

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

The ingest pipeline handles zip extraction and parsed-data refresh. After parser
changes, re-ingest the local data:

```bash
cd backend
uv run python ../scripts/reingest.py
```

Garmin Connect download support is in `scripts/download_garmin.py`. FIT structure
inspection support is in `scripts/explore_fit_files.py`.

## Validation

Backend:

```bash
cd backend
uv run ruff check
uv run pyright app/ tests/
uv run pytest tests/ -v
```

Frontend:

```bash
cd frontend
npm run check
```

If backend models or route schemas change, regenerate frontend API types:

```bash
bash scripts/generate-api-types.sh
```

Do not edit `frontend/src/lib/api-types.ts` by hand.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - current backend/frontend structure,
  ownership boundaries, and route inventory.
- [docs/DATA_SCHEMA_DESIGN.md](docs/DATA_SCHEMA_DESIGN.md) - routine, card,
  schedule, Today, and live runtime storage semantics.
- [docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md](docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md) -
  canonical routine bundle JSON contract.
- [docs/ACTIVITY_ANALYTICS_DESIGN.md](docs/ACTIVITY_ANALYTICS_DESIGN.md) - planned
  activity/session analytics and experiment-day joins.
- [FINDINGS.md](FINDINGS.md) - current observations and data quality notes from
  the live dataset.
