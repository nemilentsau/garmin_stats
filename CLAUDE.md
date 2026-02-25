# Project Rules

## Tooling & Commands
- **Python**: `uv` only (never bare `pip`). Single venv at `backend/.venv`, Python 3.12.
- **Backend**: `cd backend && uv run uvicorn app.main:app --reload`
- **Frontend**: `cd frontend && npm run dev`
- **Tests**: `cd backend && uv run pytest tests/ -v`
- **API types**: `bash scripts/generate-api-types.sh` (run after backend model changes)

## Key Constraints
- API types flow: Pydantic models → OpenAPI → generated TypeScript. Never hand-write `frontend/src/lib/api-types.ts`.
- Data format: `data/YYYY-MM-DD.zip` → extract → `YYYY-MM-DD/*.fit`. Ingest pipeline handles zip extraction.
- Period-level stats come from raw readings, never from averaging daily aggregates.

## Architecture & Reference
- Project structure, modules, backend/frontend conventions: `docs/ARCHITECTURE.md`

## Skills

Two skills support this project. Each owns specific code layers:

### `garmin-data` — FIT parsing layer
**Owns:** `parser.py`, FIT field names/types/filters, SDK quirks
**Trigger:** touching `parser.py`, adding new FIT message types, debugging parse errors, SDK upgrades
- Skill docs: `.claude/skills/garmin-data/SKILL.md`
- Verify schemas: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py`
- Discover new fields: `cd backend && uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type <TYPE>`

### `data-analysis` — aggregation + presentation layers
**Owns:** `stats.py`, aggregate stat fields in `models.py`, frontend chart configs, stat cards
**Trigger:** touching `stats.py`, adding/changing aggregate model fields, building or modifying charts
- Skill docs: `.claude/skills/data-analysis/SKILL.md`
- Pipeline traces go to `.claude/chart-inspections/<metric>-<context>/`. Never overwrite previous trace directories.

## Keeping Docs Current

Update these as part of the same PR/commit that introduces the change:
- **`README.md`**: frontend routes, API endpoints, project structure, setup instructions
- **`FINDINGS.md`**: data analysis findings, data quality observations, open questions
- Skip updates for internal refactors or code-only changes
