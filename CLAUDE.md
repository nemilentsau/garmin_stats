# Project Rules & Assumptions

**This file must be updated as we build functionality.** When you learn something new — a gotcha, a pattern that works, a mistake to avoid — add it here so it's never repeated.

## Tooling
- **Python package manager**: `uv` only. Never use bare `pip`. Use `uv pip install`, `uv run`, etc.
- **Python venv**: Root `.venv` at project root, also `backend/.venv`. Both Python 3.12 via uv.
- **Backend runner**: `uv run uvicorn app.main:app --reload` from `backend/`
- **Frontend package manager**: `npm` (standard for SvelteKit)
- **Frontend dev server**: `npm run dev` from `frontend/`

## Project Structure
- `backend/` — FastAPI app in `backend/app/` (models.py, parser.py, stats.py, main.py)
- `frontend/` — SvelteKit 2 + Svelte 5 + TailwindCSS 4 + TypeScript 5
- `data/` — Garmin FIT files organized as `data/YYYY-MM-DD/*.fit`
- FIT file naming: `{timestamp}_{TYPE}.fit` (e.g., `399375386464_SKIN_TEMP.fit`)

## Backend Conventions

### Architecture: parser → stats → SQLite → API

Two separate paths:
- **Write path (ingest):** FIT files → `parser.py` → `stats.py` → SQLite (via `database.py`)
- **Read path (API):** SQLite → reconstruct Pydantic models → `flatten_*` → JSON response

Modules:
- **`models.py`**: Pydantic models — reading atoms, day containers, API response models, ingest models
- **`parser.py`**: 3 layers — `_extract_*` (per-file), `parse_*_day` (per-day merge), `parse_*` (directory scan + date filter)
- **`stats.py`**: Aggregation/flattening — consumes typed parser output, produces API response models. No FIT knowledge.
- **`database.py`**: SQLite persistence — schema, ingest (write), read functions, fingerprinting
- **`main.py`**: FastAPI endpoints with `response_model=`, lifespan for auto-ingest

### SQLite details
- DB at `backend/garmin_stats.db` (gitignored), WAL mode, plain `sqlite3`
- JSON blobs per day (Pydantic `.model_dump_json()` / `.model_validate_json()` round-trips)
- Tables: `wellness_data`, `sleep_data`, `hrv_data`, `skin_temp_data`, `daily_metrics`, `ingest_meta`
- Auto-ingest on startup if DB is empty
- `POST /api/ingest` triggers manual re-ingest, `GET /api/ingest/status` checks if new files exist
- Data fingerprinting (SHA-256 of sorted directory listing) detects new FIT files

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

## Frontend Conventions
- Svelte 5 runes: `$props()`, `$state()`, `$effect()`, `$derived()`
- No `$:` reactive declarations (Svelte 4 syntax)
- Use `{@render children()}` not `<slot/>`
- API types generated from OpenAPI spec — run `bash scripts/generate-api-types.sh` after backend model changes
- API client in `src/lib/api.ts` — imports generated types from `api-types.ts` + `api` object with methods
- TailwindCSS 4 (imported via `@import "tailwindcss"` in app.css)
- Components go in `src/lib/components/`
- Routes in `src/routes/` following SvelteKit file-based routing
- Use `import { page } from '$app/state'` for SvelteKit page state (Svelte 5 style)
- Chart.js charts live in `src/lib/components/LineChart.svelte`, config via `src/lib/chart-setup.ts`

## API Type Generation (Single Source of Truth)
- **Pydantic models** (`backend/app/models.py`) are the source of truth for API types
- **TypeScript types** (`frontend/src/lib/api-types.ts`) are generated from the OpenAPI spec, never hand-written
- **Regenerate after model changes**: `bash scripts/generate-api-types.sh`
- The script exports `app.openapi()` → `frontend/openapi.json` → `openapi-typescript` → `frontend/src/lib/api-types.ts`
- `frontend/openapi.json` is gitignored (generated artifact)
- `frontend/src/lib/api.ts` re-exports generated types with stable frontend names (e.g., `WellnessData` = `Schemas['WellnessResponse']`)

## Svelte 5 Gotchas (learned the hard way)
- **`$derived` vs `$derived.by`**: `$derived(() => expr)` stores a *function*. `$derived.by(fn)` stores the *return value*. Always use `$derived.by` when you want the computed result.
- **Type narrowing fails in `$derived` ternaries**: `$derived(stateVar ? expr : null)` narrows `stateVar` to `never`. Always use `$derived.by(() => { if (!stateVar) return null; ... })` instead.
- **`bind:this` + `$effect`**: A plain `let` variable set by `bind:this` does NOT reliably trigger `$effect` re-runs. Use `onMount` for anything that needs the DOM element (e.g., creating a Chart.js instance on a canvas).

## Chart.js Gotchas
- **Register `CategoryScale`**: Trend charts use string date labels, which default to the `category` scale type. If `CategoryScale` is not registered in `chart-setup.ts`, charts silently fail to render.
- **Container needs `position: relative`**: Chart.js with `responsive: true` + `maintainAspectRatio: false` requires the parent container to have `position: relative`.
- **Create in `onMount`, update in `$effect`**: Create the Chart instance in `onMount` (canvas guaranteed available), use `$effect` only for reactive config updates. Return `chart.destroy()` from `onMount` for cleanup.

## Skills

Two skills support this project. Each owns specific code layers:

### `garmin-data` — FIT parsing layer
**Owns:** `parser.py`, FIT field names/types/filters, SDK quirks
**Trigger:** touching `parser.py`, adding new FIT message types, debugging parse errors, SDK upgrades
- Skill docs: `.claude/skills/garmin-data/SKILL.md`
- Trust existing schemas for documented message types — don't re-decode files for known structures
- Verify schemas: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py`
- Discover new fields: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type <TYPE>`
- Schema files in `.claude/skills/garmin-data/references/` (wellness, sleep, hrv, skin-temp, sleep-disruptions)
- Available FIT types: WELLNESS, HRV_STATUS, SLEEP_DATA, SKIN_TEMP, METRICS, SLEEP_DISRUPTIONS, NAP

### `data-analysis` — aggregation + presentation layers
**Owns:** `stats.py`, aggregate stat fields in `models.py`, frontend chart configs, stat cards, `inspect_charts.py`
**Trigger:** touching `stats.py`, adding/changing aggregate model fields, building or modifying charts, choosing what stats to show
- Skill docs: `.claude/skills/data-analysis/SKILL.md`
- This skill is project-independent — applies to any data analysis work
- Defines what statistics to compute (section 1), how to present them (sections 2-3), how to validate visually (section 4), and the pipeline trace workflow (section 6)
- **Pipeline traces** go to `.claude/chart-inspections/<metric>-<context>/` — discovery → EDA → inspection → retrospective. Required for new metrics.

## Data Context
- Date range: ~2026-01-01 to 2026-02-06 (about 37 days)
- Data volume: ~1800 HR, ~1400 stress, ~1100 SpO2, ~1400 respiration readings per day
