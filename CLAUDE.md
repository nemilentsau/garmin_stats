# Project Rules

## Tooling & Commands
- **Python**: `uv` only (never bare `pip`). Single venv at `backend/.venv`, Python 3.14.
- **Backend**: `cd backend && uv run uvicorn app.main:app --reload`
- **Frontend**: `cd frontend && npm run dev`
- **Tests**: `cd backend && uv run pytest tests/ -v`
- **Lint**: `cd backend && uv run ruff check` (checks both `app/` and `tests/`)
- **Type check**: `cd backend && uv run pyright app/ tests/`
- **API types**: `bash scripts/generate-api-types.sh` (run after backend model/route changes)
- **Validation scope rules**:
  - **Python files changed**: run backend lint + type check + tests. Iterate until all pass — 0 errors, no exceptions.
  - **Frontend/TypeScript-only changes**: run `cd frontend && npm run check` (and fix all errors).
  - **If backend API schema changed**: regenerate API types, commit updated `frontend/src/lib/api-types.ts`, then run `npm run check`.

## Visual Verification (non-negotiable)
- **All UX/frontend changes MUST be visually examined** using browser MCP tools (screenshot, read_page) before considering work complete.
- Take screenshots of every page/component modified and verify the result looks correct and is usable.
- Never ship frontend changes based solely on code review — always confirm visually in the running app.

## Key Constraints
- API types flow: Pydantic models/routes → OpenAPI → generated TypeScript.
- Never hand-write `frontend/src/lib/api-types.ts`; always regenerate via script after backend schema changes.
- Data format: `data/garmin_health_stats/YYYY-MM-DD.zip` → extract → `data/garmin_health_stats/YYYY-MM-DD/*.fit`. Ingest pipeline handles zip extraction.
- Period-level stats come from raw readings, never from averaging daily aggregates.
- Frontend is display-only: zero statistical computation. All stats, aggregations, derived values, and data transformations (moving averages, smoothing, etc.) come from the backend API. Never compute these in the frontend.
- Experiment exposures are `experiment_id + date` records, not card-level records. Derive them from whether the experiment protocol's prescribed daily dose/frequency was satisfied across all linked routine cards for that date.
- Never reduce an experiment day to a "best card status" or treat multiple linked cards on the same day as ambiguity. Multiple same-day cards are expected when the intervention dose requires multiple sessions.
- **Timestamps are local time.** FIT files store UTC; the parser extracts the per-day UTC offset from `monitoring_info_mesgs` and shifts all timestamps to local time at ingest. `DayData.utc_offset_hours` / `DailyMetric.utc_offset_hours` carry the offset for display. New timestamp fields must go through `_shift_timestamps` in `parser.py`.
- **Re-ingest after parser changes**: `cd backend && uv run python ../scripts/reingest.py`
- **Watcher/startup/ingest changes must prove no-op behavior**: if you touch startup ingest, archive extraction, watcher logic, cache invalidation, or data-root resolution, tests must cover `missing`, `already in sync`, and `stale/changed` states, including an idempotence case where a second run with no file changes does no work. After those changes, do a real local smoke check against the actual data tree before considering the task done.

## Architecture & Reference
- Project structure, modules, backend/frontend conventions: `docs/ARCHITECTURE.md`
- **Where new helpers go**: default to the closest domain. Only promote to `app/utils/` when *all three* rules hold — primitive-only signatures, no domain vocabulary in names, and two-plus consumers already exist. Read `docs/ARCHITECTURE.md` → "Shared Utilities" before adding anything to `app/utils/` or creating a new shared module.

## Skills

Five skills support this project. Each owns specific code layers:

### `garmin-data` — FIT parsing layer
**Owns:** `parser.py`, FIT field names/types/filters, SDK quirks
**Trigger:** touching `parser.py`, adding new FIT message types, debugging parse errors, SDK upgrades
- Skill docs: `.claude/skills/garmin-data/SKILL.md`
- Verify schemas: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py`
- Discover new fields: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type <TYPE>`

### `data-analysis` — aggregation + presentation layers
**Owns:** Garmin daily/period metric calculators, aggregate response fields, frontend chart configs, stat cards
**Trigger:** touching `domains/garmin_health/domain/daily_metrics/`, `domains/garmin_analytics/domain/aggregates/`, analytics contracts, or building/modifying charts
- Skill docs: `.claude/skills/data-analysis/SKILL.md`
- Pipeline traces go to `.claude/chart-inspections/<metric>-<context>/`. Never overwrite previous trace directories.

### `analytical-dashboard` — dashboard design system
**Owns:** Information hierarchy, chart selection, data visualization best practices, number formatting, interaction patterns
**Trigger:** designing or modifying any dashboard layout, choosing chart types, formatting numbers/stats, evaluating data density or readability
- Skill docs: `.claude/skills/analytical-dashboard/SKILL.md` — Tufte, Few, Knaflic principles + health platform analysis + shipping checklist
- **Read before making layout decisions** — prioritizes comprehension over aesthetics

### `ux-design` — frontend interface design (**MANDATORY** for any UI work)
**Owns:** Frontend UX aesthetics, visual styling, project-specific dashboard rules
**Trigger:** choosing fonts/colors/spacing, creating or modifying UI prototypes, visual polish
- **MUST be invoked** before designing pages or making dashboard layout changes — no exceptions
- Skill docs: `.claude/skills/ux-design/SKILL.md` — project-specific UX rules for the Garmin dashboard, assistant, Today board, and routine schedule surfaces
- Always validate frontend changes with `cd frontend && npm run check`; visually inspect every changed page with browser MCP tools

### `testing` — test discipline
**Owns:** test files in `backend/tests/`, test patterns and conventions
**Trigger:** writing or reviewing any test, adding test coverage for new features
- **Read before writing any test** — enforces equivalence-class discipline, branch/boundary coverage, and naming conventions
- For filesystem/startup code, do not stop at happy-path coverage; include the no-op second-run case.
- Skill docs: `.claude/skills/testing/SKILL.md`

## Keeping Docs Current

Update these as part of the same PR/commit that introduces the change:
- **`README.md`**: frontend routes, API endpoints, project structure, setup instructions
- **`FINDINGS.md`**: data analysis findings, data quality observations, open questions
- Skip updates for internal refactors or code-only changes
