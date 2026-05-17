# Domain Refactor Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the remaining coupling and oversized modules left after the domain refactor without changing API behavior.

**Architecture:** Keep the existing route/application/domain/adapter boundaries. Move behavior only when it clarifies ownership, removes direct adapter coupling, or shrinks files that are accumulating several reasons to change. Bootstrap remains the composition root: shared infra must not import domain packages just to initialize domain-owned tables.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, SQLite, pytest architecture guards, ruff, pyright.

---

## Task 1: Split Global SQLite Schema Ownership

**Files:**

- Delete: `backend/app/infra/database.py`
- Create: `backend/app/bootstrap/schema.py`
- Create: `backend/app/core/profile/adapters.py`
- Modify: `backend/app/bootstrap/lifespan.py`
- Modify: `backend/app/bootstrap/app.py`
- Modify: `backend/app/bootstrap/container.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/app/domains/*/schema.py` for storage-owning domains, including single-table domains when the table is domain-specific
- Create: `backend/app/core/profile/schema.py`
- Delete: `backend/app/core/profile/infra/sqlite_repository.py`
- Test: `backend/tests/infra/test_database.py`
- Test: `backend/tests/architecture/test_architecture_global_ownership.py`

- [x] Add a failing architecture test that prevents a global database module from owning domain table names such as `assistant_messages`, `routine_assignments`, `experiment_exposures`, `program_versions`, `assistant_artifacts`, `daily_checkins`, and `card_logs`.
- [x] Add small schema initializer functions beside the owning adapters, for example `init_assistant_schema(con)`, `init_routine_schema(con)`, `init_experiment_schema(con)`, `init_artifact_schema(con)`, `init_journal_schema(con)`, `init_program_schema(con)`, and `init_profile_schema(con)`.
- [x] Move the remaining profile JSON helpers into `core/profile/adapters.py` and delete the obsolete global database module.
- [x] Add `app.bootstrap.schema.init_storage()` as the composition entrypoint that opens one shared SQLite connection, enables WAL, then calls each domain/core schema initializer with that connection.
- [x] Update `lifespan.py`, `tests/conftest.py`, and any local test fixtures that initialize temporary databases to call the bootstrap schema entrypoint instead of the infra-only initializer.
- [x] Run `cd backend && uv run pytest tests/infra/test_database.py tests/architecture/test_architecture_global_ownership.py -v`.
- [x] Run `cd backend && uv run ruff check && uv run pyright app/ tests/`.

## Task 2: Split Assistant Persistence From Read-Model Gateway

**Files:**

- Modify: `backend/app/domains/assistant/adapters.py`
- Modify: `backend/app/domains/assistant/routes.py`
- Modify: `backend/app/domains/assistant/dependencies.py`
- Create: `backend/app/domains/assistant/read_gateway.py`
- Modify: `backend/app/bootstrap/container.py`
- Test: `backend/tests/architecture/test_architecture_assistant_boundaries.py`
- Test: `backend/tests/domains/assistant/`

- [x] Move thread/message/run/evidence/memory SQLite functions into an assistant conversation repository adapter.
- [x] Move cross-domain read methods from `SqliteAssistantRepository` into `AssistantReadModelGateway`.
- [x] Wire both objects in `build_container()` while preserving the `AssistantConversationStore`, `AssistantRecallStore`, and `AssistantReadModelStore` protocols. Keep `assistant_repo` as the conversation store for existing thread routes and add a distinct container field such as `assistant_read_store`.
- [x] Update `assistant/routes.py` so `post_thread_message()` passes `repo=container.assistant_repo` and `read_store=container.assistant_read_store`; thread catalog routes should continue using the conversation repository.
- [x] Add an architecture guard that `assistant/adapters.py` imports only assistant contracts/domain helpers plus SQLite/JsonStore/time utilities. Cross-domain contracts, repositories, and experiment-analysis application use cases should move to `assistant/read_gateway.py`.
- [x] Run `cd backend && uv run pytest tests/domains/assistant tests/architecture/test_architecture_assistant_boundaries.py -v`.

## Task 3: Inject Experiment Read Dependencies

**Files:**

- Modify: `backend/app/domains/experiments/dependencies.py`
- Modify: `backend/app/domains/experiments/adapters.py`
- Modify: `backend/app/domains/experiments/application/analysis.py`
- Modify: `backend/app/domains/experiments/application/analysis_cache.py`
- Modify: `backend/app/domains/experiments/application/management.py`
- Modify: `backend/app/domains/experiments/application/preview.py`
- Modify: `backend/app/domains/experiments/routes.py`
- Create: `backend/app/domains/experiments/read_sources.py`
- Modify: `backend/app/bootstrap/container.py`
- Modify: `backend/app/bootstrap/process_runtime.py`
- Test: `backend/tests/architecture/test_architecture_experiments_boundaries.py`
- Test: `backend/tests/domains/experiments/`

- [x] Add explicit experiment analysis/preview read protocols for daily Garmin metrics and journal check-ins, separate from `ExperimentRepository` persistence.
- [x] Remove direct imports of `app.domains.garmin_analytics.adapters` and `app.domains.journal.adapters` from `experiments/adapters.py`.
- [x] Pass the already-built Garmin biometric repository and journal repository through the container into the experiment read source.
- [x] Update analysis, analysis-cache, management, preview, routes, and process-runtime call sites to pass both the experiment persistence repository and the read source. Cached analysis refreshes should continue to load/save snapshots through `ExperimentRepository`, while Garmin metrics and check-ins come from the read source.
- [x] Add an architecture guard that experiment persistence does not import other domains' concrete adapters.
- [x] Run `cd backend && uv run pytest tests/domains/experiments tests/architecture/test_architecture_experiments_boundaries.py -v`.

## Task 4: Extract HRV Insight Rules and Dedupe Pattern Helpers

**Files:**

- Modify: `backend/app/domains/garmin_analytics/domain/insights/hrv.py`
- Create: `backend/app/domains/garmin_analytics/domain/insights/hrv_rules.py`
- Create: `backend/app/domains/garmin_analytics/domain/analysis/hrv_patterns.py`
- Modify: `backend/app/domains/garmin_analytics/domain/analysis/hrv.py`
- Test: `backend/tests/domains/garmin_analytics/test_hrv_service.py`

**DRY target:** `insights/hrv.py` currently imports `compute_trajectory`, `compute_hrv_distribution`, `compute_day_of_week`, and `extract_baseline_bands` back from `analysis/hrv.py`. Both layers reach for the same primitives. Promote these primitives to a single owner (`hrv_patterns.py`) and make both analysis and insights consume them.

- [x] Create `analysis/hrv_patterns.py` and move `compute_trajectory`, `compute_hrv_distribution`, `compute_day_of_week`, and `extract_baseline_bands` (plus any other primitive currently shared) into it as the single source of truth.
- [x] Rewrite `analysis/hrv.py` to import these helpers from `hrv_patterns.py` (no local copies, no re-exports except for `classify_hrv_recovery`, which is still a compatibility export used outside HRV analysis).
- [x] Rewrite `insights/hrv.py` to import the same helpers from `hrv_patterns.py` directly — never via `analysis/hrv.py`.
- [x] Move the long `_build_insights` rule chain into small named rule functions in `insights/hrv_rules.py` that each return `HrvInsight | None`.
- [x] Keep `compute_hrv_insights()` as the public selected-day composer.
- [x] Add or preserve focused tests for suppressed HRV, acute weekly gap, long low-status streak, falling overnight trajectory, long-baseline deterioration, low sample coverage, and stable recovery.
- [x] Run `cd backend && uv run pytest tests/domains/garmin_analytics/test_hrv_service.py -v`.

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

## Task 7: Split Parser File Discovery and Collapse Day-Merge Duplication

**Files:**

- Modify: `backend/app/parser.py`
- Create: `backend/app/parser_files.py`
- Create: `backend/app/parser_timestamps.py`
- Test: `backend/tests/infra/test_parser.py`
- Test: `backend/tests/domains/garmin_health/`
- Test: `backend/tests/domains/garmin_sync/`

**DRY target:** `parse_wellness_day`, `parse_sleep_day`, `parse_hrv_day`, and `parse_skin_temp_day` (parser.py:412–470) share an identical decode + extract + merge-list-fields loop. Only the extractor function and the merged-field list differ. Collapse to one parameterized helper.

- [ ] Move day-directory and FIT file grouping helpers into `parser_files.py`.
- [ ] Move Garmin timestamp parsing, compressed timestamp resolution, UTC-offset extraction, and local-time shifting into `parser_timestamps.py`.
- [ ] Introduce a single `_parse_day(files, date, *, empty, extractor, list_fields)` helper that owns the decode + try/except + per-field `extend` loop, and reduce each of the four `parse_*_day` functions to a one-line call binding its extractor and field list.
- [ ] Keep `parser.py` as the public compatibility facade for existing imports.
- [ ] Run `cd backend && uv run pytest tests/infra/test_parser.py tests/domains/garmin_health tests/domains/garmin_sync -v`.
- [ ] Because parser behavior changed, run the required local re-ingest smoke check: `cd backend && uv run python ../scripts/reingest.py`.

## Task 8: Centralize Status Filter SQL Predicate

**Files:**

- Modify: `backend/app/infra/jsonstore.py`
- Modify: `backend/app/domains/routines/adapters.py`
- Modify: `backend/app/domains/programs/adapters.py`
- Modify: `backend/app/domains/experiments/adapters.py`
- Modify: `backend/app/domains/artifacts/adapters.py`
- Test: `backend/tests/infra/test_jsonstore.py`

**DRY target:** The literal SQL fragment `json_extract(data, '$.status') = ?` (and its `IN ({placeholders})` variant) is duplicated across `routines/adapters.py:46,71`, `programs/adapters.py:39`, `experiments/adapters.py:45`, and `artifacts/adapters.py:52,75`. Centralize the predicate so JSON-payload field paths and placeholder building live in one place.

- [ ] Add a small helper on `JsonStore` (or a sibling module) such as `status_predicate(values: Sequence[str]) -> tuple[str, tuple[object, ...]]` that returns the `where_sql` fragment and params tuple, supporting both single-value and `IN (...)` cases.
- [ ] Generalize the helper so any allowlisted JSON field path can be filtered (e.g. `json_field_predicate(path, values)`), since `artifacts/adapters.py` also filters on `$.kind` and `$.payload_json.id`. Do not interpolate arbitrary caller-provided paths into SQL.
- [ ] Define empty-value behavior explicitly: callers that pass an empty sequence should get a predicate that matches no rows, or adapters should return early before building a query. Do not emit invalid `IN ()` SQL.
- [ ] Update each adapter listed above to use the helper instead of building the SQL string locally.
- [ ] Verify no behavior change with unit tests that exercise single-value, multi-value, and empty-value cases, plus an adapter-level behavior test for at least one status filter and the artifact payload-id lookup.
- [ ] Run `cd backend && uv run pytest tests/infra tests/domains/routines tests/domains/programs tests/domains/experiments tests/domains/artifacts -v`.

## Final Verification

- [ ] Run `cd backend && uv run ruff check`.
- [ ] Run `cd backend && uv run pyright app/ tests/`.
- [ ] Run `cd backend && uv run pytest tests/ -v`.
- [ ] If any backend route or Pydantic schema changes unexpectedly, run `bash scripts/generate-api-types.sh` from the repo root and then `cd frontend && npm run check`.
