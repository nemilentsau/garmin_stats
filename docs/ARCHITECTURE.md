# Architecture

## Project Structure
- `backend/` — FastAPI app in `backend/app/` (models.py, parser.py, stats.py, main.py, infra/, utils/)
- `backend/tests/` — pytest tests for stats and database
- `frontend/` — SvelteKit 2 + Svelte 5 + TailwindCSS 4 + TypeScript 5
- `storage/` — SQLite database (gitignored, auto-created on startup)
- `data/` — Garmin health data. Raw input is `.zip` archives, unpacked form is `YYYY-MM-DD/*.fit`
  - **Input format:** `data/YYYY-MM-DD.zip` — flat zip containing `.fit` files (no subdirectory inside)
  - **Unpacked format:** `data/YYYY-MM-DD/*.fit` — created by extracting the zip into a same-named directory
  - The watcher/ingest pipeline must handle `.zip` → extract → parse `.fit` files
- FIT file naming: `{timestamp}_{TYPE}.fit` (e.g., `399375386464_SKIN_TEMP.fit`)

## Design References
- `docs/DATA_SCHEMA_DESIGN.md` — routine runtime design, card philosophy, explicit and implicit schema assumptions

## Backend

### Data flow: parser → stats → SQLite → API

Two separate paths:
- **Write path (ingest):** FIT files → `parser.py` → `stats.py` → SQLite (via `database.py`)
- **Read path (API):** SQLite → reconstruct Pydantic models → `flatten_*` → JSON response

### Modules

Domain core (app root):
- **`models.py`**: Pydantic models — reading atoms, day containers, API response models, ingest models
- **`parser.py`**: 3 layers — `_extract_*` (per-file), `parse_*_day` (per-day merge), `parse_*` (directory scan + date filter)
- **`stats.py`**: Aggregation/flattening — consumes typed parser output, produces API response models. No FIT knowledge.
- **`main.py`**: App creation, CORS middleware, lifespan (auto-ingest + file watcher + heartbeat tasks), router registration. All endpoints live in `routers/`.

Infrastructure (`infra/`):
- **`infra/database.py`**: SQLite persistence — schema, ingest (write), read functions, fingerprinting
- **`infra/cache.py`**: In-memory cache with generation-based invalidation
- **`infra/events.py`**: SSE event bus — `EventBus` with per-client `asyncio.Queue`, module-level `event_bus` singleton
- **`infra/watcher.py`**: File watcher — `watch_data_directory()` uses `watchfiles.awatch()` to detect new `.zip` files, auto-ingests, broadcasts `data_updated` via SSE; `heartbeat_loop()` keeps connections alive

Utilities (`utils/`):
- **`utils/timeutil.py`**: Shared time helpers (ISO-8601 parsing)
- **`routers/`**: Domain-specific HTTP route modules. Each defines an `APIRouter` with a prefix and delegates to `database`/`stats`/`services`:
  - `ingest.py` (`/api/ingest`) — trigger re-ingest, check ingest status
  - `days.py` (`/api/days`) — list available days, get day summary
  - `wellness.py` (`/api/wellness`) — wellness data (HR, stress, SpO2, respiration, activity)
  - `sleep.py` (`/api/sleep`) — sleep data (stages, assessment scores)
  - `daily_aggregates.py` (`/api/daily-aggregates`) — per-day aggregate stats + period summary
  - `skin_temp.py` (`/api/skin-temp`) — skin temperature data
  - `heart_rate.py` (`/api/heart-rate`) — heart rate insights + analysis + distribution
  - `hrv.py` (`/api/hrv`) — HRV data + insights
  - `events.py` (`/api/events`) — SSE stream for real-time updates
  - `routines.py` (`/api/routines`) — live routines, recurring assignments, and 14-day resolved schedule windows

- **`services/`**: Domain-level business logic — pure functions + DB loaders for derived insights:
  - `heart_rate.py` — day-level HR insights: recovery, zone durations, quality metrics
  - `heart_rate_analysis.py` — period-level HR analysis: circadian profile, sleeping HR trend (cross-date sleep-stage correlation), resting HR trend (7-day MA), HR distribution (5-bpm histogram), weekly boxplots (5-number summary by ISO week)
  - `hrv.py` — day-level HRV insights: recovery, intraday segments (day/night split), status mix, trend bands
  - `schedule_projection.py` — backend-owned recurrence resolution for 14-day dated schedule windows shared by Schedule and Today

### SQLite details
- DB at `storage/garmin_stats.db` (gitignored), WAL mode, plain `sqlite3`
- Configurable via env vars: `GARMIN_DB_PATH`, `GARMIN_DATA_DIR` (defaults: `storage/garmin_stats.db`, `data/`)
- JSON blobs per day (Pydantic `.model_dump_json()` / `.model_validate_json()` round-trips)
- Tables: `wellness_data`, `sleep_data`, `hrv_data`, `skin_temp_data`, `daily_metrics`, `ingest_meta`
- `ingest_meta` also stores `period_summary` (precomputed period-level stats from raw data)
- Auto-ingest on startup if DB is empty
- `POST /api/ingest` triggers manual re-ingest, `GET /api/ingest/status` checks if new files exist
- Data fingerprinting (SHA-256 of sorted directory listing) detects new FIT files
- Connection management via `_connect()` context manager (never manual try/finally)
- Table name whitelist (`_VALID_TABLES`) prevents SQL injection in dynamic queries

### Key patterns
- Parser returns typed Pydantic models (e.g., `list[DayWellness]`), not dicts
- `parse_all_days(data_dir)` scans the directory **once** for all metrics (used during ingest)
- `flatten_*` functions concatenate per-day lists into flat API responses (same as before, data sourced from DB)
- Use `get_files_by_day()` to discover files, filter by type key (e.g., "SKIN_TEMP", "WELLNESS")
- Use `decode_fit_file()` to read FIT files, returns `{message_type: [messages]}`
- Use `parse_datetime()` for timestamp conversion
- Filter invalid values (e.g., -1, -2 for stress; -1 for respiration)
- API endpoints at `/api/...`, return JSON, use HTTPException(404) for missing data
- Use `logging.warning()` for parse errors (not `print()`)

### Testing
- Tests in `backend/tests/` — run with `cd backend && uv run pytest tests/ -v`
- `test_stats.py`: helpers, aggregate_day, compute_period_summary, flatten functions
- `test_database.py`: schema init, round-trip storage, period summary, table whitelist
- All DB tests use `tmp_path` fixture (isolated temp DB per test)

## Frontend

### Conventions
- Svelte 5 runes: `$props()`, `$state()`, `$effect()`, `$derived()`
- No `$:` reactive declarations (Svelte 4 syntax)
- Use `{@render children()}` not `<slot/>`
- API client in `src/lib/api.ts` — imports generated types from `api-types.ts` + `api` object with methods
- SSE client in `src/lib/sse.ts` — `createDataUpdateListener(onUpdate)` subscribes to `GET /api/events`, calls callback on `data_updated`, returns cleanup function for `onMount`
- Shared utilities: `src/lib/format.ts` (`fmt()` for number display), `src/lib/colors.ts` (chart color palette)
- Chart colors: always use `COLORS` from `$lib/colors`, never hardcode hex values in routes
- Use `catch (e: unknown)` with `e instanceof Error` narrowing, never `catch (e: any)`
- TailwindCSS 4 (imported via `@import "tailwindcss"` in app.css)
- Components go in `src/lib/components/`
- Routes in `src/routes/` following SvelteKit file-based routing
- Use `import { page } from '$app/state'` for SvelteKit page state (Svelte 5 style)
- Chart.js charts live in `src/lib/components/LineChart.svelte` and `BarChart.svelte`, config via `src/lib/chart-setup.ts`
- **Frontend is display-only** — zero statistical computation. All stats, aggregations, zone distributions, and derived values are computed on the backend. Frontend only handles chart config, formatting, and rendering.
- Period-level stats come from `data.period` (backend-computed from raw readings), never from averaging daily aggregates

### API Type Generation
- **Pydantic models** (`backend/app/models.py`) are the source of truth for API types
- **TypeScript types** (`frontend/src/lib/api-types.ts`) are generated from the OpenAPI spec, never hand-written
- **Regenerate after model changes**: `bash scripts/generate-api-types.sh`
- The script exports `app.openapi()` → `frontend/openapi.json` → `openapi-typescript` → `frontend/src/lib/api-types.ts`
- `frontend/openapi.json` is gitignored (generated artifact)
- `frontend/src/lib/api.ts` re-exports generated types with stable frontend names (e.g., `WellnessData` = `Schemas['WellnessResponse']`)

### Svelte 5 Gotchas
- **`$derived` vs `$derived.by`**: `$derived(() => expr)` stores a *function*. `$derived.by(fn)` stores the *return value*. Always use `$derived.by` when you want the computed result.
- **Type narrowing fails in `$derived` ternaries**: `$derived(stateVar ? expr : null)` narrows `stateVar` to `never`. Always use `$derived.by(() => { if (!stateVar) return null; ... })` instead.
- **`bind:this` + `$effect`**: A plain `let` variable set by `bind:this` does NOT reliably trigger `$effect` re-runs. Use `onMount` for anything that needs the DOM element (e.g., creating a Chart.js instance on a canvas).

### Chart.js Gotchas
- **Register `CategoryScale`**: Trend charts use string date labels, which default to the `category` scale type. If `CategoryScale` is not registered in `chart-setup.ts`, charts silently fail to render.
- **Container needs `position: relative`**: Chart.js with `responsive: true` + `maintainAspectRatio: false` requires the parent container to have `position: relative`.
- **Create in `onMount`, update in `$effect`**: Create the Chart instance in `onMount` (canvas guaranteed available), use `$effect` only for reactive config updates. Return `chart.destroy()` from `onMount` for cleanup.

## Data Context
- Date range: ~2026-01-01 to 2026-02-06 (about 37 days)
- Data volume: ~1800 HR, ~1400 stress, ~1100 SpO2, ~1400 respiration readings per day
