# Routine Ownership Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move live routine runtime contracts out of the global `app.models` bucket and make routine consumers depend on the routines slice explicitly.

**Architecture:** Add `backend/app/domains/routines/contracts.py` for live card, schedule, Today, and card-log models. Keep `app.models` as a transitional re-export so existing tests and generated schema names stay stable, while production modules import routine-owned types directly. Update architecture guardrails so the cleanup is measurable.

**Tech Stack:** FastAPI, Pydantic, SQLite repository adapters, pytest architecture tests, ruff, pyright.

---

### Task 1: Add Routine-Owned Contracts

**Files:**
- Create: `backend/app/domains/routines/contracts.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/architecture/test_architecture_global_ownership.py`

- [x] Create `contracts.py` with `RendererFamily`, `SlotName`, `WeekdayName`, `CardLogStatus`, `CardOverrideAction`, `ScheduleOccurrenceSourceKind`, `CardTemplate`, `RoutineSchedule`, `RoutineAssignment`, `CardLog`, `CardOverride`, Today response models, schedule response models, and response wrappers.
- [x] Remove the live routine class definitions from `app.models` and import those names from `app.domains.routines.contracts` instead.
- [x] Keep artifact draft specs in `app.models`: `CardTemplateSpec`, `RoutineAssignmentSpec`, `RoutineSpec`, `ArtifactBundleSpec`, and related artifact response models stay where they are in this phase.
- [x] Run `cd backend && uv run pytest tests/architecture/test_architecture_global_ownership.py -v` and expect the existing allowlist to fail until production imports move.

### Task 2: Move Production Imports To Routine Contracts

**Files:**
- Modify: `backend/app/domains/routines/**/*.py`
- Modify: `backend/app/domains/artifacts/**/*.py`
- Modify: `backend/app/domains/experiments/application/exposure_sync.py`
- Modify: `backend/app/domains/assistant/application/ports.py`
- Modify: `backend/app/domains/assistant/application/retrieval.py`
- Modify: `backend/app/domains/assistant/infra/sqlite_repository.py`
- Modify: `backend/app/infra/database.py`

- [x] Change routines API, application, domain, and infra modules to import live routine models from `app.domains.routines.contracts`.
- [x] Change artifacts modules that read or write live `CardTemplate` records to import that type from routines contracts while leaving artifact draft specs in `app.models`.
- [x] Change experiment exposure sync to import `CardLog` and `ScheduleOccurrence` from routines contracts.
- [x] Change assistant read-model ports and retrieval code to import `CardLog`, `RoutineAssignment`, and `RoutineSchedule` from routines contracts.
- [x] Change `app.infra.database` routine persistence type imports to use routines contracts.

### Task 3: Tighten Guardrails And Verify

**Files:**
- Modify: `backend/tests/architecture/test_architecture_global_ownership.py`
- Modify: `backend/tests/architecture/test_architecture_cross_slice_imports.py`
- Optional regenerate: `frontend/src/lib/api-types.ts`

- [x] Remove migrated routine modules from `ALLOWLISTED_APP_MODELS_IMPORTERS` when they no longer import `app.models`.
- [x] Add explicit cross-slice allowlist entries for consumers that now import `app.domains.routines.contracts`.
- [x] Run `cd backend && uv run ruff check app/ tests/`.
- [x] Run `cd backend && uv run pyright app/ tests/`.
- [x] Run `cd backend && uv run pytest tests/ -v`.
- [x] If OpenAPI output changes, run `bash scripts/generate-api-types.sh` and then `cd frontend && npm run check`.
