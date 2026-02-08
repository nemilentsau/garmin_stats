# Project Rules & Assumptions

**This file must be updated as we build functionality.** When you learn something new — a gotcha, a pattern that works, a mistake to avoid — add it here so it's never repeated.

## Tooling
- **Python package manager**: `uv` only. Never use bare `pip`. Use `uv pip install`, `uv run`, etc.
- **Python venv**: Root `.venv` at project root, also `backend/.venv`. Both Python 3.12 via uv.
- **Backend runner**: `uv run uvicorn app.main:app --reload` from `backend/`
- **Frontend package manager**: `npm` (standard for SvelteKit)
- **Frontend dev server**: `npm run dev` from `frontend/`

## Project Structure
- `backend/` — FastAPI app in `backend/app/` (main.py, parser.py)
- `frontend/` — SvelteKit 2 + Svelte 5 + TailwindCSS 4 + TypeScript 5
- `data/` — Garmin FIT files organized as `data/YYYY-MM-DD/*.fit`
- FIT file naming: `{timestamp}_{TYPE}.fit` (e.g., `399375386464_SKIN_TEMP.fit`)

## Backend Conventions
- Parser functions follow pattern: `parse_X_data(data_dir: Path, date: str | None = None) -> dict`
- Use `get_files_by_day()` to discover files, filter by type key (e.g., "SKIN_TEMP", "WELLNESS")
- Use `decode_fit_file()` to read FIT files, returns `{message_type: [messages]}`
- Use `parse_datetime()` for timestamp conversion
- Filter invalid values (e.g., -1, -2 for stress; -1 for respiration)
- API endpoints at `/api/...`, return JSON, use HTTPException(404) for missing data

## Frontend Conventions
- Svelte 5 runes: `$props()`, `$state()`, `$effect()`, `$derived()`
- No `$:` reactive declarations (Svelte 4 syntax)
- Use `{@render children()}` not `<slot/>`
- API client in `src/lib/api.ts` — typed interfaces + `api` object with methods
- TailwindCSS 4 (imported via `@import "tailwindcss"` in app.css)
- Components go in `src/lib/components/`
- Routes in `src/routes/` following SvelteKit file-based routing
- Use `import { page } from '$app/state'` for SvelteKit page state (Svelte 5 style)
- Chart.js charts live in `src/lib/components/LineChart.svelte`, config via `src/lib/chart-setup.ts`

## Svelte 5 Gotchas (learned the hard way)
- **`$derived` vs `$derived.by`**: `$derived(() => expr)` stores a *function*. `$derived.by(fn)` stores the *return value*. Always use `$derived.by` when you want the computed result.
- **Type narrowing fails in `$derived` ternaries**: `$derived(stateVar ? expr : null)` narrows `stateVar` to `never`. Always use `$derived.by(() => { if (!stateVar) return null; ... })` instead.
- **`bind:this` + `$effect`**: A plain `let` variable set by `bind:this` does NOT reliably trigger `$effect` re-runs. Use `onMount` for anything that needs the DOM element (e.g., creating a Chart.js instance on a canvas).

## Chart.js Gotchas
- **Register `CategoryScale`**: Trend charts use string date labels, which default to the `category` scale type. If `CategoryScale` is not registered in `chart-setup.ts`, charts silently fail to render.
- **Container needs `position: relative`**: Chart.js with `responsive: true` + `maintainAspectRatio: false` requires the parent container to have `position: relative`.
- **Create in `onMount`, update in `$effect`**: Create the Chart instance in `onMount` (canvas guaranteed available), use `$effect` only for reactive config updates. Return `chart.destroy()` from `onMount` for cleanup.

## Garmin FIT SDK Gotchas
- **HR uses `timestamp_16`, not `timestamp`**: Heart rate entries in `monitoring_mesgs` use a compressed 16-bit timestamp field (`timestamp_16`), NOT the standard `timestamp` field. Calling `msg.get("timestamp")` returns `None` for HR entries. To associate HR data with a day, use the file's parent directory name (the date).
- **Multiple WELLNESS files per day**: The watch splits WELLNESS data into sequential time chunks. Always iterate all WELLNESS files for a given day.
- **SKIN_TEMP**: 1 reading per night via `skin_temp_overnight_mesgs`. Fields: `timestamp`, `local_timestamp`, `nightly_value`, `average_deviation`, `average_7_day_deviation`, plus unknown field `3`.

## Data Notes
- Available FIT types: WELLNESS, HRV_STATUS, SLEEP_DATA, SKIN_TEMP, METRICS, SLEEP_DISRUPTIONS
- Date range: ~2026-01-01 to 2026-02-06 (about 37 days)
