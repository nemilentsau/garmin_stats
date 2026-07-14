# Garmin Health Coach

Garmin Health Assistant is a local-first personal health application built around
Garmin wellness exports. It ingests Garmin FIT files, turns them into deterministic
recovery metrics, and presents them through a Svelte dashboard, a routine execution
surface, and a coach that reviews training from bounded local evidence.

The project is pivoting from recovery-first observation to goal-directed
training (see `docs/routine-pivot/`). The primary product flow today is
dashboard + coach + the **v3 training block**: authored training artifacts
are uploaded through `Training → Import`, validated by a build-time linter, and
executed on the Today board with native capture. The older v2 routine runtime
remains as the import path for non-training bundles (meditation, breathwork);
experiments sit on top of it. Content of any kind enters the app **only** via
import — there are no generators, seeders, or derived artifacts.

## What It Does

- Imports daily Garmin health archives from `data/garmin_health_stats/`.
- Parses FIT files into local-time records and stores derived data in SQLite.
- Computes all statistics in the backend, including daily metrics, period
  summaries, moving averages, a validated single-axis recovery score with health
  flags, and metric insights.
- Renders a frontend recovery dashboard whose overview is the recovery score —
  a state-before-score banner, a shared-axis trajectory, an evidence table of what
  moved it, and oxygen/thermoregulation flags — with full metric drill-downs for
  HRV, sleep, heart rate, stress, body battery, respiration, skin temperature, and
  pulse ox. See [docs/reference/recovery-dashboard.md](docs/reference/recovery-dashboard.md).
- Tracks the next central-dashboard lanes separately from the recovery score. Sleep opportunity,
  health exceptions, and experiment adherence can build from existing data/contracts; load and
  progress build on the activity/session ingestion that has now started (running is shipped; see
  below). See
  [docs/future/central-dashboard-readiness.md](docs/future/central-dashboard-readiness.md).
- Imports v3 training artifacts (bundles, block, signal registry, exercise
  library) as-is through `Training → Import`, lints them (L1–L12), and executes
  the active block on the Today board with native capture: per-set strength
  logs, tissue check-in, run RPE, and variant branch logging.
- Downloads tracked-activity FIT files from Garmin Connect during sync into
  `data/garmin_activities/`. Running activities are fully parsed into session/
  lap/series tables and shown at `/runs` and `/runs/[id]` with Garmin-parity
  detail (strap channels, stamina/performance-condition, a GPS route map,
  imperial display units); a tracked run is also associated with the
  prescribed run card it satisfies and surfaced on the Today board. Strength
  and breathing activity files still download-only. See
  [docs/reference/run-activities.md](docs/reference/run-activities.md).
- Provides queued run reviews and coach chat from existing analytics, a 20-run
  digest with on-demand detail, semantic journal/brief memory, and strict evidence
  limits. See [docs/reference/coach.md](docs/reference/coach.md).
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
  -> backend/app/domains/garmin_health/infra/fit_parser/
  -> Garmin health daily metric composer
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
vertical module structure with explicit ownership contracts. Some modules are
product domains, some are operational capabilities, and some are analytical read
models; the boundary rules matter more than the package label:

- `bootstrap/` assembles the FastAPI app, registers routers, owns lifespan wiring,
  and provides the dependency container.
- `infra/` contains shared infrastructure primitives: SQLite connection/schema
  bootstrap, JSON-row helpers, and cache invalidation. Realtime transport and
  Garmin file watching live in dedicated app/domain capabilities.
- `domains/garmin_sync/` is a Garmin data acquisition capability. It owns
  `/api/ingest`, Garmin Connect wellness archive download orchestration, archive
  extraction, ingest status, and affected-date ingest decisions.
- `domains/garmin_health/` owns canonical Garmin health contracts, FIT parsing,
  timestamp normalization, and daily metric composition used by ingest
  persistence, analytics, experiments, and coach evidence reads.
- `domains/garmin_analytics/` owns Garmin-derived read models, dashboard data,
  biometric reads, recovery insights, analyses, and period summaries.
- `domains/coach/` owns durable reviews/threads/jobs, hierarchical evidence
  workspaces, semantic journal/brief memory, plot packaging, and isolated Codex
  execution. It reuses analytics/training/journal read models rather than owning
  estimators.
- `domains/routines/` owns routine catalog, schedule projection, Today execution,
  and routine activation.
- `domains/artifacts/` owns authored card/routine artifacts, bundle
  preview/import, capability requests, and card-template persistence before
  delegating live routine activation to `domains/routines`.
- `domains/experiments/` owns experiment definitions, target metrics, exposure
  derivation, and N=1 analysis with flat routes/adapters/dependencies and pure
  experiment rules in `domain/`.
- `domains/journal/` owns daily check-ins and notes.
- `domains/training/` owns v3 training artifact import/activation, the ported
  L1-L12 block linter, schedule compilation, and Today/schedule-window/
  block-status read models for imported training content. It stays independent
  from `domains/routines`; the frontend composes both feeds, while Coach reads
  training through its explicit gateway/contracts.
- `core/profile/` owns app-level profile configuration.

Current strict-boundary slices follow the same convention: route/API modules
handle FastAPI and dependency lookup, workflow/application modules own
orchestration without importing SQLite helpers or the dependency container, and
adapter modules are the infrastructure boundary. Repository and callable
dependencies live in `dependencies.py`; API and persistence shapes live in
`contracts.py`. Larger slices may split large route or contract surfaces into
packages, while small capability slices prefer clearer flat names like
`routes.py`, `adapters.py`, `dependencies.py`, and `contracts.py`. Any future
transitional slices should be explicitly allowlisted in architecture tests with
their permitted boundary violations.

The frontend is a SvelteKit app under `frontend/src/`. It renders the recovery
overview, metric detail pages, Coach, Today board, and routine schedule
review. Shared API helpers and generated API types live in `frontend/src/lib/`.

For the full current code map and route inventory, see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Routine Runtime

Routines are imported through deterministic bundle JSON (`schema_version: 2`),
not freeform markdown. The normal flow is:

```text
bundle JSON -> preview -> import -> auto-activate -> schedule and Today
```

Preview validates without writing. Import persists validated artifacts and
activates cards before routines, because routines depend on card templates. Today
logs execution for a date; it does not author schedule structure.

Routine bundle assignments are explicit and day-relative. Activation compiles
them into dated `RoutineAssignment` rows; the frontend does not compute schedule
math.

### Card types

Each card template carries a typed `payload` with a `card_type` discriminator.
(These are the v2 routine-bundle card types; **training cards are separate** —
they follow the v3 schema in `docs/routine-pivot/schema_v3_spec.md` and enter
only through the training import.) The five card types are:

| `card_type` | Domain | Key payload fields |
|---|---|---|
| `running_workout` | Running | `workout_type`, `segments`, `post_run_fields` |
| `strength_session` | Strength | `exercises` (set_scheme), `rating_prompts` |
| `breath_timer` | Breathwork | `pattern_label`, `duration_minutes` (logs one `felt_downshift`) |
| `meditation_timer` | Meditation | `technique`, `anchor` |
| `checklist` | Any (via `domain`) | `items`, `domain` |

`payload_json` and `actual_json` on live runtime models (`CardTemplate`,
`ScheduleOccurrence`, `TodayCard`, `CardLog`) are fully typed discriminated
unions keyed on `card_type`. The OpenAPI schema exposes this union;
`frontend/src/lib/api-types.ts` is generated from it (never hand-written).

### Importing bundles

To preview, import, and activate every bundle in `docs/routine_bundles/`:

```bash
cd backend && uv run python ../scripts/import_bundles.py
```

The script previews each bundle first (no writes on failure), then imports and
activates. It writes to the configured database; set `GARMIN_DB_PATH` to
override the default path.

The bundle format is documented in
[docs/routine_bundles/ROUTINE_ARTIFACT_BUNDLE_SPEC.md](docs/routine_bundles/ROUTINE_ARTIFACT_BUNDLE_SPEC.md).
Example bundles live in `docs/routine_bundles/`.

Importing a bundle is the only way routine or experiment content enters the
app — there is no generation, translation, or seeding path. The v3 training
artifacts in `docs/routine-pivot/block1/` are the active authored block;
`block0/` remains the frozen schema exemplar and test-fixture canon.

### Training import

`domains/training` is a separate, standalone slice that imports v3 training
artifacts natively — it does not go through the `domains/routines` bundle
pipeline above. The frontend route is `/training/import`: select the six
artifact files (`running_v3.json`, `strength_v3.json`, `support_v3.json`,
`block1.json`, `registry.json`, `exercise_library.json`) and import. Import is
single-shot and all-or-nothing — every file must be independently
contract-valid, the set must be complete relative to the block's own
`bundle_ids`, the ported L1-L12 block linter must report zero errors, and any
lint warnings must be explicitly acknowledged; otherwise nothing is written
and the whole set stays unwritten. A successful import activates the block
and bundles atomically, retiring any previously active block.

Backend endpoints:

- `POST /api/training/import` — upload and activate a full artifact set.
- `GET /api/training/block` — the active block's definition, lint report, and
  current day.
- `GET /api/training/today` — Today's training cards (`/today` renders these
  next to routine cards, feed by feed).
- `GET /api/training/schedule-window` — the schedule projection consumed by
  `/routines/schedule`.
- `PUT /api/training/today/{date}/cards/{occurrence_key}` — persist a
  training card's status, variant selection, notes, and capture log (set/rep/
  load, RPE, or check-in soreness/flags, depending on card type).

## Repository Layout

```text
backend/
  app/          FastAPI app, domain slices, parser, analytics, infrastructure
  tests/        Backend tests organized by architecture, infra, core, and domain
frontend/
  src/          SvelteKit routes, components, API client, chart helpers
scripts/        Local utility scripts for Garmin download, ingest, FIT inspection
docs/           Architecture notes, design direction, bundle specs, examples
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

Garmin Connect download support is in `scripts/download_garmin.py`. By default it
downloads daily wellness archives. Tracked activity FIT files can be downloaded
with `--activities`; Garmin returns one original ZIP per activity and the script
extracts each FIT plus metadata under `data/garmin_activities/YYYY-MM-DD/`.
Activity filenames use local start time plus decoded FIT `sport` and
`sub_sport`, for example `104056_running_generic.fit` or
`105002_training_strength_training.fit`; the Garmin activity id is kept in the
JSON sidecar and is only appended to filenames if two activities would otherwise
collide.

```bash
cd backend
uv run python ../scripts/download_garmin.py --activities --date 2026-06-27
```

To backfill tracked activities across the same inclusive date range represented
by the existing health archive data:

```bash
cd backend
uv run python ../scripts/download_garmin.py --activities --health-range
```

The dashboard's Sync button (`POST /api/ingest/sync`) also downloads new
tracked-activity FIT files automatically, alongside the wellness archives, for
the wellness ingest window plus a 3-day lookback. Files land under
`data/garmin_activities/YYYY-MM-DD/`; running activities are then parsed into
session/lap/series tables on that same sync (and on startup), while strength
and breathing files remain download-only, not yet parsed or ingested into the
database. Activities uploaded to Garmin Connect later than that 3-day lookback
window are not fetched by the Sync button — backfill them with
`scripts/download_garmin.py --activities` (`--from`/`--to` or
`--health-range`). The sync response reports counts via
`activities_downloaded` / `activities_skipped` / `activities_failed`, but only
the downloaded-workouts count is shown in the sync result line; skipped and
failed counts are API-only. After a parser-field change, re-parse
already-downloaded activity files with `scripts/reingest_activities.py` — see
[docs/reference/data-and-ingest.md](docs/reference/data-and-ingest.md) for
details.

FIT structure inspection support is in `scripts/explore_fit_files.py`.

Runtime path overrides are centralized in backend app config:

- `GARMIN_DB_PATH`
- `GARMIN_DATA_DIR`
- `GARMIN_ACTIVITY_DATA_DIR`
- `GARMINTOKENS`

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

- [docs/README.md](docs/README.md) - documentation index and source-of-truth
  guide.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - current backend/frontend structure,
  ownership boundaries, and route inventory.
- [docs/reference/data-and-ingest.md](docs/reference/data-and-ingest.md) - the
  two Garmin data trees, ingest/sync mechanics, and config paths.
- [docs/reference/run-activities.md](docs/reference/run-activities.md) - how
  tracked runs parse, store, and display.
- [docs/reference/recovery-dashboard.md](docs/reference/recovery-dashboard.md) - the recovery score, health
  flags, and dashboard overview design reference.
- [docs/reference/recovery-score.md](docs/reference/recovery-score.md) - product explanation and critique of
  the recovery score as one lane of the dashboard.
- [docs/future/central-dashboard-readiness.md](docs/future/central-dashboard-readiness.md) - current
  central-dashboard roadmap and data-readiness summary.
- [docs/routine_bundles/ROUTINE_ARTIFACT_BUNDLE_SPEC.md](docs/routine_bundles/ROUTINE_ARTIFACT_BUNDLE_SPEC.md) -
  canonical routine bundle JSON contract.
- [docs/future/ACTIVITY_ANALYTICS_DESIGN.md](docs/future/ACTIVITY_ANALYTICS_DESIGN.md) - planned
  activity/session analytics and experiment-day joins.
- [FINDINGS.md](FINDINGS.md) - current observations and data quality notes from
  the live dataset.
