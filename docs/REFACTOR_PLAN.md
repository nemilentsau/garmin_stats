# Domain Refactor Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the remaining coupling and oversized modules left after the domain refactor without changing API behavior.

**Architecture:** Keep the existing route/application/domain/adapter boundaries. Move behavior only when it clarifies ownership, removes direct adapter coupling, or shrinks files that are accumulating several reasons to change.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, SQLite, pytest architecture guards, ruff, pyright.

---

## Task 1: Split Global SQLite Schema Ownership

**Files:**

- Modify: `backend/app/infra/database.py`
- Modify: `backend/app/bootstrap/lifespan.py`
- Create: `backend/app/domains/*/schema.py` only for domains that own multiple tables
- Test: `backend/tests/infra/test_database.py`
- Test: `backend/tests/architecture/test_architecture_global_ownership.py`

- [ ] Add a failing architecture test that prevents `backend/app/infra/database.py` from containing domain table names such as `assistant_messages`, `routine_assignments`, `experiment_exposures`, and `program_versions`.
- [ ] Add small schema initializer functions beside the owning adapters, for example `init_assistant_schema(con)`, `init_routine_schema(con)`, and `init_experiment_schema(con)`.
- [ ] Keep `app.infra.database.init_db()` as the composition entrypoint, but make it call domain schema initializers instead of embedding all domain DDL in one string.
- [ ] Run `cd backend && uv run pytest tests/infra/test_database.py tests/architecture/test_architecture_global_ownership.py -v`.
- [ ] Run `cd backend && uv run ruff check && uv run pyright app/ tests/`.

## Task 2: Split Assistant Persistence From Read-Model Gateway

**Files:**

- Modify: `backend/app/domains/assistant/adapters.py`
- Create: `backend/app/domains/assistant/read_gateway.py`
- Modify: `backend/app/bootstrap/container.py`
- Test: `backend/tests/architecture/test_architecture_assistant_boundaries.py`
- Test: `backend/tests/domains/assistant/`

- [ ] Move thread/message/run/evidence/memory SQLite functions into an assistant conversation repository adapter.
- [ ] Move cross-domain read methods from `SqliteAssistantRepository` into `AssistantReadModelGateway`.
- [ ] Wire both objects in `build_container()` while preserving the `AssistantConversationStore`, `AssistantRecallStore`, and `AssistantReadModelStore` protocols.
- [ ] Add an architecture guard that `assistant/adapters.py` does not import experiment, routine, Garmin analytics, journal, or profile contracts except where conversation persistence actually needs assistant-owned contracts.
- [ ] Run `cd backend && uv run pytest tests/domains/assistant tests/architecture/test_architecture_assistant_boundaries.py -v`.

## Task 3: Inject Experiment Read Dependencies

**Files:**

- Modify: `backend/app/domains/experiments/dependencies.py`
- Modify: `backend/app/domains/experiments/adapters.py`
- Create: `backend/app/domains/experiments/read_sources.py`
- Modify: `backend/app/bootstrap/container.py`
- Test: `backend/tests/architecture/test_architecture_experiments_boundaries.py`
- Test: `backend/tests/domains/experiments/`

- [ ] Add explicit experiment analysis read protocols for daily Garmin metrics and journal check-ins.
- [ ] Remove direct imports of `app.domains.garmin_analytics.adapters` and `app.domains.journal.adapters` from `experiments/adapters.py`.
- [ ] Pass the already-built Garmin biometric repository and journal repository through the container into the experiment read source.
- [ ] Add an architecture guard that experiment persistence does not import other domains' concrete adapters.
- [ ] Run `cd backend && uv run pytest tests/domains/experiments tests/architecture/test_architecture_experiments_boundaries.py -v`.

## Task 4: Extract HRV Insight Rules

**Files:**

- Modify: `backend/app/domains/garmin_analytics/domain/insights/hrv.py`
- Create: `backend/app/domains/garmin_analytics/domain/insights/hrv_rules.py`
- Create: `backend/app/domains/garmin_analytics/domain/analysis/hrv_patterns.py`
- Modify: `backend/app/domains/garmin_analytics/domain/analysis/hrv.py`
- Test: `backend/tests/domains/garmin_analytics/test_hrv_service.py`

- [ ] Move the long `_build_insights` rule chain into small named rule functions that each return `HrvInsight | None`.
- [ ] Move shared HRV pattern helpers used by both analysis and insights, such as distribution, trajectory, baseline bands, and day-of-week grouping, into `hrv_patterns.py`.
- [ ] Keep `compute_hrv_insights()` as the public selected-day composer.
- [ ] Add or preserve focused tests for suppressed HRV, acute weekly gap, long low-status streak, falling overnight trajectory, long-baseline deterioration, low sample coverage, and stable recovery.
- [ ] Run `cd backend && uv run pytest tests/domains/garmin_analytics/test_hrv_service.py -v`.

## Task 5: Decompose Experiment Preview

**Files:**

- Modify: `backend/app/domains/experiments/application/preview.py`
- Create: `backend/app/domains/experiments/domain/design_dates.py`
- Create: `backend/app/domains/experiments/domain/preview_validation.py`
- Modify: `backend/app/domains/experiments/domain/metric_paths.py`
- Test: `backend/tests/domains/experiments/`

- [ ] Replace in-place mutation of `experiment.design` with a copied design returned from date-resolution helpers.
- [ ] Move baseline/treatment date rules into `design_dates.py`.
- [ ] Move check-in field validation next to path resolution so `preview.py` does not hard-code `DailyCheckIn` field names.
- [ ] Keep `preview_experiment()` as orchestration only: resolve dates, load metrics, call validators, assemble response.
- [ ] Run `cd backend && uv run pytest tests/domains/experiments -v`.

## Task 6: Split Assistant Chat Turn Orchestration

**Files:**

- Modify: `backend/app/domains/assistant/application/chat.py`
- Create: `backend/app/domains/assistant/application/turn_context.py`
- Create: `backend/app/domains/assistant/application/runtime_stream.py`
- Test: `backend/tests/domains/assistant/test_assistant_chat_application.py`

- [ ] Move route/entity/memory/evidence preparation into a pure `prepare_turn_context()` helper.
- [ ] Move runtime event consumption and assistant-message assembly into `stream_runtime_reply()`.
- [ ] Keep `stream_reply()` responsible for transaction order and emitted JSON line events.
- [ ] Preserve failure persistence behavior for runs.
- [ ] Run `cd backend && uv run pytest tests/domains/assistant/test_assistant_chat_application.py -v`.

## Task 7: Split Parser File Discovery From FIT Extraction

**Files:**

- Modify: `backend/app/parser.py`
- Create: `backend/app/parser_files.py`
- Create: `backend/app/parser_timestamps.py`
- Test: `backend/tests/domains/garmin_health/`
- Test: `backend/tests/domains/garmin_sync/`

- [ ] Move day-directory and FIT file grouping helpers into `parser_files.py`.
- [ ] Move Garmin timestamp parsing, compressed timestamp resolution, UTC-offset extraction, and local-time shifting into `parser_timestamps.py`.
- [ ] Keep `parser.py` as the public compatibility facade for existing imports.
- [ ] Run `cd backend && uv run pytest tests/domains/garmin_health tests/domains/garmin_sync -v`.

## Final Verification

- [ ] Run `cd backend && uv run ruff check`.
- [ ] Run `cd backend && uv run pyright app/ tests/`.
- [ ] Run `cd backend && uv run pytest tests/ -v`.
- [ ] If any backend route or Pydantic schema changes unexpectedly, run `bash scripts/generate-api-types.sh` from the repo root and then `cd frontend && npm run check`.
