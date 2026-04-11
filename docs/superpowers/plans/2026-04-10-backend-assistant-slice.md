# Backend Assistant Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Date: 2026-04-10
Status: Approved next slice

**Goal:** Move assistant thread, message, run, context, and runtime orchestration into `backend/app/domains/assistant/` while keeping the current `/api/assistant` HTTP contract stable.

**Architecture:** This slice follows the same migration pattern used for `domains/routines/`: domain-local `api`, `application`, and `infra` packages behind stable HTTP routes plus compatibility wrappers at the old flat entrypoints. Assistant artifact and bundle routes stay externally stable in this slice and remain on the existing `training_specs.py` seam until artifact ownership is intentionally revisited.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLite, pytest, uv, ruff, pyright

---

## Scope Note

This plan covers only the assistant chat/runtime vertical slice:

1. `/api/assistant/threads`
2. `/api/assistant/threads/{thread_id}`
3. `/api/assistant/threads/{thread_id}/messages`
4. streamed assistant reply orchestration
5. assistant context snapshot building
6. assistant runtime integration and event publishing seams

This plan does not move assistant artifacts or bundle import routes yet. Those stay externally stable on `training_specs.py` during this slice.

## File Map

### Create

- `backend/app/domains/assistant/__init__.py`
  Domain package marker.

- `backend/app/domains/assistant/api/__init__.py`
  API package marker for assistant routes.

- `backend/app/domains/assistant/api/threads.py`
  Domain-local `/api/assistant` routes for threads, messages, and streamed replies.

- `backend/app/domains/assistant/application/__init__.py`
  Application package marker.

- `backend/app/domains/assistant/application/ports.py`
  Protocols for assistant repository, runtime, context snapshot builder, and event publishing.

- `backend/app/domains/assistant/application/threads.py`
  Use cases for list/create/get thread and list messages.

- `backend/app/domains/assistant/application/chat.py`
  Use case for streamed assistant replies and run lifecycle orchestration.

- `backend/app/domains/assistant/infra/__init__.py`
  Infrastructure package marker.

- `backend/app/domains/assistant/infra/sqlite_repository.py`
  SQLite-backed adapter for assistant threads, messages, runs, and snapshots.

- `backend/app/domains/assistant/infra/runtime.py`
  Adapter around the existing Claude Code runtime implementation.

- `backend/app/domains/assistant/infra/context_snapshot.py`
  Adapter that builds context snapshots from current metrics, routines, experiments, notes, and profile state.

- `backend/app/domains/assistant/infra/events.py`
  Adapter for publishing assistant run and streaming events.

- `backend/tests/test_assistant_threads_application.py`
  Application-level tests for thread and message catalog behavior.

- `backend/tests/test_assistant_chat_application.py`
  Application-level tests for streamed assistant reply orchestration.

- `backend/tests/test_architecture_assistant_boundaries.py`
  Import and layering guard tests for the assistant slice.

### Modify

- `backend/app/bootstrap/container.py`
  Add assistant repository/runtime/context/events wiring.

- `backend/app/bootstrap/routing.py`
  Mount the domain-local assistant router.

- `backend/app/routers/assistant.py`
  Convert to a compatibility wrapper around the domain-local assistant router.

- `backend/app/services/assistant.py`
  Replace orchestration logic with compatibility wrappers over assistant application use cases.

- `backend/app/services/assistant_runtime.py`
  Keep only the low-level runtime adapter or delegate into `domains/assistant/infra/runtime.py`.

- `backend/app/services/assistant_context.py`
  Keep only the low-level snapshot builder or delegate into `domains/assistant/infra/context_snapshot.py`.

- `backend/tests/test_phase2_routes.py`
  Keep public HTTP coverage stable while the route ownership moves.

- `backend/tests/test_assistant_service.py`
  Re-point orchestration tests toward assistant application seams where appropriate.

- `backend/tests/test_assistant_runtime.py`
  Preserve runtime-wrapper behavior checks as the infra adapter is introduced.

- `backend/tests/test_assistant_context.py`
  Preserve context snapshot behavior checks as the infra adapter is introduced.

## Task 1: Establish The Assistant Domain Skeleton

**Files:**
- Create: `backend/app/domains/assistant/**/*`
- Modify: `backend/app/bootstrap/container.py`

- [ ] Create the `domains/assistant/{api,application,infra}` package structure.
- [ ] Define `AssistantRepository`, `AssistantRuntime`, `ContextSnapshotBuilder`, and `AssistantEventPublisher` protocols in `application/ports.py`.
- [ ] Extend `bootstrap/container.py` so assistant dependencies are resolved from the same composition root as the routines slice.
- [ ] Keep `app.main` and the current router registration behavior stable while the new package structure is introduced.

## Task 2: Move Thread And Message Catalog Use Cases

**Files:**
- Create: `backend/app/domains/assistant/application/threads.py`
- Create: `backend/app/domains/assistant/infra/sqlite_repository.py`
- Modify: `backend/app/services/assistant.py`
- Test: `backend/tests/test_assistant_threads_application.py`

- [ ] Extract list/create/get thread and list messages behavior into `application/threads.py`.
- [ ] Implement the SQLite-backed repository adapter using the existing assistant tables and low-level database helpers.
- [ ] Update `services/assistant.py` so the flat module becomes a compatibility wrapper over the new application use cases.
- [ ] Add application seam tests for thread ordering, missing-thread behavior, and message listing.
- [ ] Keep existing route response shapes unchanged.

## Task 3: Move Streamed Chat Orchestration

**Files:**
- Create: `backend/app/domains/assistant/application/chat.py`
- Create: `backend/app/domains/assistant/infra/runtime.py`
- Create: `backend/app/domains/assistant/infra/context_snapshot.py`
- Create: `backend/app/domains/assistant/infra/events.py`
- Modify: `backend/app/services/assistant.py`
- Modify: `backend/app/services/assistant_runtime.py`
- Modify: `backend/app/services/assistant_context.py`
- Test: `backend/tests/test_assistant_chat_application.py`

- [ ] Move `stream_thread_reply()` orchestration into `application/chat.py`.
- [ ] Treat runtime execution, context snapshot construction, and event publishing as explicit dependencies injected through ports.
- [ ] Reuse the existing runtime and context logic by wrapping it in domain-local infra adapters instead of copying behavior.
- [ ] Preserve current run lifecycle semantics: user message persisted first, run started, deltas streamed, assistant reply saved on success, run marked failed on error.
- [ ] Add seam tests for success, runtime failure, and setup failure paths.

## Task 4: Move The HTTP Boundary

**Files:**
- Create: `backend/app/domains/assistant/api/threads.py`
- Modify: `backend/app/bootstrap/routing.py`
- Modify: `backend/app/routers/assistant.py`
- Modify: `backend/tests/test_phase2_routes.py`

- [ ] Mount a domain-local assistant router from `domains/assistant/api/threads.py`.
- [ ] Keep `backend/app/routers/assistant.py` as an import-compatible wrapper, just as the routines slice kept flat route wrappers.
- [ ] Keep the existing `/api/assistant` paths, request models, response models, and NDJSON streaming behavior unchanged.
- [ ] Re-point route tests so monkeypatches and assertions follow the new domain-local ownership.

## Task 5: Enforce Assistant Boundaries And Verify The Slice

**Files:**
- Create: `backend/tests/test_architecture_assistant_boundaries.py`
- Modify: `backend/tests/test_assistant_service.py`
- Modify: `backend/tests/test_assistant_runtime.py`
- Modify: `backend/tests/test_assistant_context.py`

- [ ] Add architecture tests that reject domain API imports of low-level database helpers and reject FastAPI imports in assistant application modules.
- [ ] Require the flat `routers/assistant.py` module to remain a compatibility wrapper rather than a second real owner of the routes.
- [ ] Run the required verification commands:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

- [ ] Do not claim the slice complete until all three commands pass on the merged branch state.

## Out Of Scope For This Slice

- `backend/app/routers/assistant_artifacts.py`
- `backend/app/routers/assistant_artifact_bundles.py`
- artifact validation/import logic in `backend/app/services/training_specs.py`
- any intentional ownership redesign for artifact bundles versus routines

Those concerns stay externally stable until the chat/runtime slice is complete.

## Recommended Follow-Up Order After This Plan

1. Execute this assistant slice.
2. Plan and migrate `domains/garmin_analytics/`.
3. Move `experiments`, `programs`, and `profile` out of the flat service/route buckets.
4. Remove obsolete compatibility seams and continue shrinking `models.py` and `stats.py`.
