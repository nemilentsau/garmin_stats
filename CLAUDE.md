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
- This is a desktop web app today, not a mobile app. Default visual verification is the normal desktop browser viewport; do not run mobile breakpoints, touch-target audits, or mobile screenshots unless the task explicitly targets responsive/mobile behavior.
- Never ship frontend changes based solely on code review — always confirm visually in the running app.

## Key Constraints
- API types flow: Pydantic models/routes → OpenAPI → generated TypeScript.
- Never hand-write `frontend/src/lib/api-types.ts`; always regenerate via script after backend schema changes.
- **Data sources & ingest:** two Garmin trees — wellness (`garmin_health_stats/`, ingested → `daily_metrics`) and tracked activities (`garmin_activities/`, downloaded from Garmin Connect every sync, parse/associate pending). Topology, config paths, and commands are in `docs/reference/data-and-ingest.md` (single source of truth) — do not restate paths here.
- Period-level stats come from raw readings, never from averaging daily aggregates.
- **Display units are US imperial** (user rule, 2026-07-11): distance in miles, pace in min/mi, elevation in feet, temperature in °F — matching the user's Garmin Connect profile. Never display km or min/km. Storage and canonical contracts stay FIT-native metric; the backend read layer converts and serves display-ready imperial fields. Garmin-style exceptions stay metric: stride length (m), vertical oscillation (cm), ground contact time (ms).
- Frontend is display-only: zero statistical computation. All stats, aggregations, derived values, and data transformations (moving averages, smoothing, etc.) come from the backend API. Never compute these in the frontend.
- Experiment exposures are `experiment_id + date` records, not card-level records. Derive them from whether the experiment protocol's prescribed daily dose/frequency was satisfied across all linked routine cards for that date.
- Never reduce an experiment day to a "best card status" or treat multiple linked cards on the same day as ambiguity. Multiple same-day cards are expected when the intervention dose requires multiple sessions.
- **Timestamps are local time** (invariant): FIT stores UTC; the parser shifts all timestamps to local at ingest, and `utc_offset_hours` carries the offset for display. New timestamp fields must be shifted at ingest — parser internals are owned by the `garmin-data` skill; data topology and the re-ingest command live in `docs/reference/data-and-ingest.md`.
- **Watcher/startup/ingest changes must prove no-op behavior**: if you touch startup ingest, archive extraction, watcher logic, cache invalidation, or data-root resolution, tests must cover `missing`, `already in sync`, and `stale/changed` states, including an idempotence case where a second run with no file changes does no work. After those changes, do a real local smoke check against the actual data tree before considering the task done.
- **Import is the only content ingress.** Routine, experiment, and training content enters the app exclusively by importing/uploading an authored bundle. Never write generators, translators, seeders, or "derived" bundle artifacts — not even as a temporary bridge. The app adapts to new schemas (currently v3: `docs/routine-pivot/schema_v3_spec.md` + `block0/` artifacts, which are canon and read-only); schemas are never flattened into older engine formats.

## Where Things Live (map)
This file holds durable rules, setup, and pointers — not current-state facts. For detail, go to the one authoritative doc:
- **Code map** — domains, dependency layering, boundaries, route inventory: `docs/ARCHITECTURE.md`
- **Data sources, ingest, sync, config paths**: `docs/reference/data-and-ingest.md`
- **How shipped features work** (recovery dashboard, HRV tab, …): `docs/reference/`
- **Training system canon** (P1–P13 principles, v3 schema, roadmap, block0): `docs/routine-pivot/`
- **Specs for unbuilt work**: `docs/future/`
- **Doc index / question router**: `docs/README.md`
- **Code conventions** (app/utils promotion rule, slice boundaries, frontend, doc style): `docs/reference/code-conventions.md`
- **Route inventory** (generated): `docs/reference/routes.md` — regenerate via `scripts/generate_routes_doc.py`
- **Where new helpers go**: default to the closest domain; promote to `app/utils/` only when all three hold — primitive-only signatures, no domain vocabulary in names, two-plus consumers exist (`docs/reference/code-conventions.md`).

## Code Documentation Style
Docstring/comment conventions (boundary-first, ownership, lifecycle, when to add class/function/test docstrings) live in `docs/reference/code-conventions.md`. Keep in-code docs current in the same change that moves the code.

## Skills

Six skills support this project. Each owns specific code layers:

### `garmin-data` — FIT parsing layer
**Owns:** `backend/app/domains/garmin_health/infra/fit_parser/`, the `backend/app/parser.py` compatibility facade, FIT field names/types/filters, SDK quirks
**Trigger:** touching FIT parser modules or the parser facade, adding new FIT message types, debugging parse errors, SDK upgrades
- Skill docs: `.claude/skills/garmin-data/SKILL.md`
- Verify schemas: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py`
- Discover new fields: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type <TYPE>`

### `data-analysis` — aggregation + presentation layers
**Owns:** Garmin daily/period metric calculators, aggregate response fields, frontend chart configs, stat cards
**Trigger:** touching `domains/garmin_health/domain/daily_metrics/`, `domains/garmin_analytics/domain/aggregates/`, analytics contracts, or building/modifying charts
- Skill docs: `.claude/skills/data-analysis/SKILL.md`
- Pipeline traces go to `.claude/chart-inspections/<metric>-<context>/`. Never overwrite previous trace directories.

### `finding-analyst` — health-data investigation workflow
**Owns:** Question-led, exploratory, and scout analysis runs over the Garmin dataset; `FINDINGS.md` evidence and update policy
**Trigger:** investigating a question about the dataset, reviewing a metric area, running a scout pass for candidate signals, or proposing a `FINDINGS.md` update
- Skill docs: `.claude/skills/finding-analyst/SKILL.md` — run types, confidence tiers, recipes (`RECIPES.md`), and report templates
- Findings land in `FINDINGS.md`; chart inspections reuse the `data-analysis` trace convention under `.claude/chart-inspections/`

### `analytical-dashboard` — dashboard design system
**Owns:** Information hierarchy, chart selection, data visualization best practices, number formatting, interaction patterns
**Trigger:** designing or modifying any dashboard layout, choosing chart types, formatting numbers/stats, evaluating data density or readability
- Skill docs: `.claude/skills/analytical-dashboard/SKILL.md` — Tufte, Few, Knaflic principles + health platform analysis + shipping checklist
- **Read before making layout decisions** — prioritizes comprehension over aesthetics

### `ux-design` — frontend interface design (**MANDATORY** for any UI work)
**Owns:** Frontend UX aesthetics, visual styling, project-specific dashboard rules
**Trigger:** choosing fonts/colors/spacing, creating or modifying UI prototypes, visual polish
- **MUST be invoked** before designing pages or making dashboard layout changes — no exceptions
- Skill docs: `.claude/skills/ux-design/SKILL.md` — project-specific UX rules for the Garmin dashboard, assistant, Today board, and routine schedule surfaces. Includes the **"Cards Are a Last Resort" forcing rule** — apply it before any card/grid layout; the per-metric detail tabs are exempt.
- Always validate frontend changes with `cd frontend && npm run check`; visually inspect every changed page with browser MCP tools at the desktop web viewport unless mobile/responsive behavior is explicitly in scope

### `testing` — test discipline
**Owns:** test files in `backend/tests/`, test patterns and conventions
**Trigger:** writing or reviewing any test, adding test coverage for new features
- **Read before writing any test** — enforces equivalence-class discipline, branch/boundary coverage, and naming conventions
- For filesystem/startup code, do not stop at happy-path coverage; include the no-op second-run case.
- Skill docs: `.claude/skills/testing/SKILL.md`

## Keeping Docs Current

Each fact has exactly one authoritative home; every other mention links to it. Update the owning doc in the same PR/commit that changes the thing:
- **`docs/reference/data-and-ingest.md`**: data trees, ingest/sync, config paths, data commands
- **`backend/app/domains/<d>/CHARTER.md`**: that domain's boundary contract (Owns / does-not-own / imports / entrypoints) when the domain changes
- **`docs/reference/routes.md`**: regenerate via `scripts/generate_routes_doc.py` after route changes
- **`docs/ARCHITECTURE.md`**: the domain index + code map when a domain is added/removed or the dependency layering changes
- **`README.md`**: product overview, setup, high-level data-flow narrative — link to the detail, don't restate paths
- **`FINDINGS.md`**: data analysis findings, data quality observations, open questions
- Skip updates for internal refactors or code-only changes

**CLAUDE.md acid test:** before adding a line here, ask "will this still be true after a normal refactor?" If it names a path, filename, or command a refactor would move, it belongs in the owning doc — not in this always-loaded file.

Docs hygiene rules:
- **Implementation plans and working specs are never committed to `docs/`.** Write them to the gitignored `.superpowers/` scratch area (or the session scratchpad); they are working artifacts, deleted with the work. Git history is the archive.
- `docs/` follows the taxonomy in `docs/README.md`: `routine-pivot/` (canon) · `ARCHITECTURE.md` (code map) · `reference/` (how shipped things work) · `future/` (specs for unbuilt work) · `routine_bundles/` (legacy v2 content) · `findings/`. A doc whose subject stops existing is deleted in the same change.
