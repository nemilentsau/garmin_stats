# Backend Bootstrap And Routines Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Date: 2026-04-08
Status: Completed and merged into `refactor` on 2026-04-10

**Goal:** Split backend app bootstrap out of `backend/app/main.py`, create the first domain-local backend slice under `backend/app/domains/routines/`, and migrate routines schedule/today/runtime logic behind unchanged HTTP routes.

**Architecture:** This plan implements the first milestone from `docs/superpowers/specs/2026-04-08-backend-domain-modular-monolith-design.md`, not the entire backend end state. Keep the public HTTP API stable, route old flat modules through compatibility wrappers, and move routines behavior into `domains/routines/{api,application,domain,infra}` with repository adapters instead of direct router-to-database access.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLite, pytest, uv, ruff, pyright

---

## Execution Outcome

This plan has been executed and merged into `refactor`.

Delivered:

- bootstrap split into `backend/app/bootstrap/{app,lifespan,routing,container}.py`
- `backend/app/core/config.py` extracted out of `main.py`
- first domain-local backend slice created under `backend/app/domains/routines/`
- routines catalog, schedule-window, today, and activation logic moved into domain-local application code
- flat routines/today routers and services converted into compatibility seams
- architecture guard tests added for the routines slice
- backend packaging normalized around `pyproject.toml` and `uv.lock`
- backend interpreter target moved to Python 3.14 during the prerequisite cleanup

Follow-up fixes that landed before merge:

- routine activation now writes schedule plus assignments atomically
- `training_specs.py` now resolves the routines repository lazily instead of freezing it at import time
- startup ingest tests now cover the second-run no-op path
- `docs/ARCHITECTURE.md` was updated to reflect the migrated bootstrap and routines slice

Merged verification:

- `cd backend && uv run ruff check`
- `cd backend && uv run pyright app/ tests/`
- `cd backend && uv run pytest tests/ -v`

All three passed on the merged `refactor` branch, with `pytest` at `308 passed`.

## Historical Note

The checkbox tasks below are preserved as the original execution plan. The source of truth for what actually landed is the execution outcome above plus the current code on `refactor`.

## Next Step

The next recommended implementation slice is the assistant chat/runtime domain. See `docs/superpowers/plans/2026-04-10-backend-assistant-slice.md`.

## Scope Note

This plan intentionally covers only the first executable refactor slice:

1. bootstrap split from `backend/app/main.py`
2. initial shared core extraction via `backend/app/core/config.py`
3. routines domain package skeleton
4. routines application use cases for catalog, schedule window, today, and routine activation
5. compatibility wrappers for old flat services and routers
6. boundary tests and full backend verification

Everything else from the approved design gets its own follow-up plan.

## File Map

### Create

- `backend/app/core/config.py`
  Parse backend config that should not stay embedded in app assembly, starting with CORS origins.

- `backend/app/bootstrap/__init__.py`
  Package marker for bootstrap modules.

- `backend/app/bootstrap/app.py`
  FastAPI app factory, middleware wiring, exception handlers, root route, and top-level assembly.

- `backend/app/bootstrap/lifespan.py`
  Startup ingest reconciliation, watcher task setup, and shutdown cancellation.

- `backend/app/bootstrap/routing.py`
  Register all app routers in one place so `main.py` stops owning routing.

- `backend/app/bootstrap/container.py`
  Minimal dependency container for the routines repository used by the first domain slice.

- `backend/app/domains/__init__.py`
  Domain package marker.

- `backend/app/domains/routines/__init__.py`
  Routines domain package marker.

- `backend/app/domains/routines/api/__init__.py`
  API package marker for routines routes.

- `backend/app/domains/routines/api/routines.py`
  `/api/routines` routes backed by routines application services.

- `backend/app/domains/routines/api/today.py`
  `/api/today` routes backed by routines application services.

- `backend/app/domains/routines/application/__init__.py`
  Application package marker for routines use cases.

- `backend/app/domains/routines/application/ports.py`
  Repository protocol for routines use cases.

- `backend/app/domains/routines/application/catalog.py`
  Use cases for list/get routines and routine assignments.

- `backend/app/domains/routines/application/schedule_window.py`
  Use case for schedule projection.

- `backend/app/domains/routines/application/today.py`
  Use cases for today board reads, log updates, and card log range reads.

- `backend/app/domains/routines/application/activation.py`
  Use case for compiling a validated `routine_spec` artifact into live schedules and assignments.

- `backend/app/domains/routines/domain/__init__.py`
  Domain package marker for routines.

- `backend/app/domains/routines/domain/schedule.py`
  Pure schedule helpers such as slot ordering, date parsing, and occurrence key building.

- `backend/app/domains/routines/infra/__init__.py`
  Infrastructure package marker for routines.

- `backend/app/domains/routines/infra/sqlite_repository.py`
  SQLite-backed repository adapter that wraps existing `app.infra.database` helpers.

- `backend/tests/test_bootstrap_app.py`
  Tests for `create_app()` and bootstrap assembly.

- `backend/tests/test_routines_catalog_application.py`
  Tests for routines catalog use cases.

- `backend/tests/test_routines_schedule_application.py`
  Tests for the domain-local schedule window use case.

- `backend/tests/test_routines_today_application.py`
  Tests for the domain-local today use case.

- `backend/tests/test_routines_activation_application.py`
  Tests for compiling routine artifacts through the routines domain.

- `backend/tests/test_architecture_routines_boundaries.py`
  Low-cost import/boundary guards for the new routines slice.

### Modify

- `backend/app/main.py`
  Reduce to a compatibility entrypoint that exposes `app = create_app()`.

- `backend/app/routers/routines.py`
  Replace with a compatibility wrapper that re-exports the new domain router and handlers.

- `backend/app/routers/today.py`
  Replace with a compatibility wrapper that re-exports the new domain router and handlers.

- `backend/app/services/schedule_projection.py`
  Replace logic with a compatibility wrapper around `domains.routines.application.schedule_window`.

- `backend/app/services/today.py`
  Replace logic with a compatibility wrapper around `domains.routines.application.today`.

- `backend/app/services/training_specs.py`
  Delegate routines list/get/assignments and routine activation to routines domain application modules while keeping assistant artifact APIs stable.

- `backend/tests/test_main.py`
  Point startup and route monkeypatches at bootstrap/domain modules instead of the old `app.main` internals.

- `backend/tests/test_training_specs.py`
  Keep compatibility coverage but update imports and assertions where the routines domain now owns the behavior.

## Task 1: Split Bootstrap Assembly Out Of `main.py`

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/bootstrap/__init__.py`
- Create: `backend/app/bootstrap/app.py`
- Create: `backend/app/bootstrap/lifespan.py`
- Create: `backend/app/bootstrap/routing.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_main.py`
- Test: `backend/tests/test_bootstrap_app.py`

- [ ] **Step 1: Write the failing bootstrap tests**

Create `backend/tests/test_bootstrap_app.py`:

```python
"""Bootstrap app-factory tests."""

from app.bootstrap.app import create_app


def test_create_app_returns_configured_fastapi_instance():
    app = create_app()

    assert app.title == "Garmin Stats API"
    assert any(route.path == "/" for route in app.routes)
```

Update `backend/tests/test_main.py` so startup tests patch bootstrap-lifespan helpers instead of `app.main` internals:

```python
import app.bootstrap.lifespan as lifespan_mod
import app.main as main_mod
from app.models import IngestResult, IngestStatus


class TestStartupIngest:
    def test_runs_ingest_after_reconciling_existing_archives(self, monkeypatch):
        order: list[str] = []

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 3

        def fake_check_ingest_status(_data_dir):
            assert order == ["extract"]
            return IngestStatus(
                needs_ingest=True,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=58,
                days_on_disk=72,
            )

        def fake_ingest_all(_data_dir):
            order.append("ingest")
            return IngestResult(days_ingested=72, duration_ms=321)

        monkeypatch.setattr(lifespan_mod, "extract_existing_archives", fake_extract_existing_archives)
        monkeypatch.setattr(lifespan_mod, "check_ingest_status", fake_check_ingest_status)
        monkeypatch.setattr(lifespan_mod, "ingest_all", fake_ingest_all)

        lifespan_mod.run_startup_ingest_if_needed()
```

- [ ] **Step 2: Run the focused tests and verify the import failure**

Run:

```bash
cd backend && uv run pytest tests/test_bootstrap_app.py tests/test_main.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'app.bootstrap'
```

- [ ] **Step 3: Implement bootstrap modules and keep `app.main` as a compatibility entrypoint**

Create `backend/app/core/config.py`:

```python
"""Shared backend configuration helpers."""

from __future__ import annotations

import os

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5180",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5180",
]


def get_cors_origins() -> list[str]:
    raw = os.environ.get("BACKEND_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or DEFAULT_CORS_ORIGINS
```

Create `backend/app/bootstrap/lifespan.py`:

```python
"""FastAPI lifespan and startup ingest helpers."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infra.database import DATA_DIR, check_ingest_status, ingest_all, init_db
from app.infra.watcher import extract_existing_archives, heartbeat_loop, watch_data_directory

log = logging.getLogger(__name__)


def task_done_callback(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        log.error("Background task %s failed: %s", task.get_name(), exc, exc_info=exc)


def run_startup_ingest_if_needed() -> None:
    extract_existing_archives(DATA_DIR)
    status = check_ingest_status(DATA_DIR)
    if not status.needs_ingest:
        log.info(
            "Startup data already in sync: %d days in DB, %d days on disk",
            status.days_in_db,
            status.days_on_disk,
        )
        return

    log.info(
        "%s — running startup ingest",
        "DB empty" if status.days_in_db == 0 else "Data directory changed",
    )
    result = ingest_all(DATA_DIR)
    log.info("Startup ingest complete: %d days in %d ms", result.days_ingested, result.duration_ms)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    run_startup_ingest_if_needed()

    watcher_task = asyncio.create_task(watch_data_directory(DATA_DIR), name="file-watcher")
    watcher_task.add_done_callback(task_done_callback)
    heartbeat_task = asyncio.create_task(heartbeat_loop(), name="sse-heartbeat")
    heartbeat_task.add_done_callback(task_done_callback)
    try:
        yield
    finally:
        watcher_task.cancel()
        heartbeat_task.cancel()
```

Create `backend/app/bootstrap/routing.py`:

```python
"""Router registration for the FastAPI app."""

from fastapi import FastAPI

from app.routers.assistant import router as assistant_router
from app.routers.assistant_artifact_bundles import router as assistant_artifact_bundles_router
from app.routers.assistant_artifacts import router as assistant_artifacts_router
from app.routers.body_battery import router as body_battery_router
from app.routers.cards import router as cards_router
from app.routers.checkins import router as checkins_router
from app.routers.daily_aggregates import router as daily_aggregates_router
from app.routers.dashboard import router as dashboard_router
from app.routers.days import router as days_router
from app.routers.events import router as events_router
from app.routers.experiments import router as experiments_router
from app.routers.heart_rate import router as heart_rate_router
from app.routers.hrv import router as hrv_router
from app.routers.ingest import router as ingest_router
from app.routers.notes import router as notes_router
from app.routers.profile import router as profile_router
from app.routers.programs import router as programs_router
from app.routers.routines import router as routines_router
from app.routers.skin_temp import router as skin_temp_router
from app.routers.sleep import router as sleep_router
from app.routers.stress import router as stress_router
from app.routers.target_metrics import router as target_metrics_router
from app.routers.today import router as today_router
from app.routers.wellness import router as wellness_router


def register_routers(app: FastAPI) -> None:
    for router in [
        ingest_router,
        dashboard_router,
        days_router,
        wellness_router,
        sleep_router,
        daily_aggregates_router,
        skin_temp_router,
        heart_rate_router,
        hrv_router,
        stress_router,
        body_battery_router,
        events_router,
        assistant_router,
        assistant_artifact_bundles_router,
        assistant_artifacts_router,
        cards_router,
        profile_router,
        routines_router,
        checkins_router,
        notes_router,
        experiments_router,
        target_metrics_router,
        programs_router,
        today_router,
    ]:
        app.include_router(router)
```

Create `backend/app/bootstrap/app.py`:

```python
"""FastAPI app factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_cors_origins
from app.infra.database import DATA_DIR

from .lifespan import lifespan
from .routing import register_routers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Garmin Stats API",
        description="API for analyzing Garmin Epix Gen 2 health data",
        version="0.1.0",
        separate_input_output_schemas=True,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LookupError)
    async def lookup_error_handler(_request: Request, exc: LookupError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.middleware("http")
    async def disable_api_response_caching(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/")
    def root():
        return {
            "status": "ok",
            "message": "Garmin Stats API",
            "data_dir": str(DATA_DIR),
            "data_exists": DATA_DIR.exists(),
        }

    register_routers(app)
    return app
```

Replace `backend/app/main.py` with:

```python
"""Compatibility ASGI entrypoint."""

from app.bootstrap.app import create_app

app = create_app()

__all__ = ["app", "create_app"]
```

- [ ] **Step 4: Run the focused bootstrap tests**

Run:

```bash
cd backend && uv run pytest tests/test_bootstrap_app.py tests/test_main.py -v
```

Expected:

```text
tests/test_bootstrap_app.py::test_create_app_returns_configured_fastapi_instance PASSED
tests/test_main.py::TestCacheHeaders::test_api_routes_send_no_store_headers PASSED
tests/test_main.py::TestStartupIngest::test_runs_ingest_after_reconciling_existing_archives PASSED
```

- [ ] **Step 5: Commit the bootstrap split**

Run:

```bash
git add backend/app/core/config.py backend/app/bootstrap backend/app/main.py backend/tests/test_bootstrap_app.py backend/tests/test_main.py
git commit -m "refactor: split FastAPI bootstrap wiring"
```

## Task 2: Create The Routines Domain Catalog Scaffold

**Files:**
- Create: `backend/app/bootstrap/container.py`
- Create: `backend/app/domains/__init__.py`
- Create: `backend/app/domains/routines/__init__.py`
- Create: `backend/app/domains/routines/application/__init__.py`
- Create: `backend/app/domains/routines/application/ports.py`
- Create: `backend/app/domains/routines/application/catalog.py`
- Create: `backend/app/domains/routines/infra/__init__.py`
- Create: `backend/app/domains/routines/infra/sqlite_repository.py`
- Test: `backend/tests/test_routines_catalog_application.py`

- [ ] **Step 1: Write the failing catalog-use-case tests**

Create `backend/tests/test_routines_catalog_application.py`:

```python
"""Tests for routines catalog use cases."""

from app.domains.routines.application.catalog import (
    get_routine,
    list_routine_assignments,
    list_routines,
)
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.models import AssistantArtifactCreateRequest
from app.services.training_specs import activate_assistant_artifact, create_assistant_artifact


def _card_request(card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": "timer_session",
            "slot_default": "morning",
            "summary": "Catalog fixture card",
            "tags": ["training"],
            "payload": {"duration_minutes": 10, "pattern": "5s in / 5s out", "instructions": "Stay relaxed."},
        },
    )


def _routine_request(routine_id: str, *, card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Catalog fixture",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def test_list_routines_reads_live_schedules():
    repo = SqliteRoutineRepository()
    response = list_routines(repo, status="active")
    assert response.routines == []


def test_get_routine_and_assignments_read_same_routine():
    repo = SqliteRoutineRepository()
    card_artifact = create_assistant_artifact(_card_request("card-catalog"))
    activate_assistant_artifact(card_artifact.id)
    artifact = create_assistant_artifact(_routine_request("routine-catalog", card_id="card-catalog"))
    activate_assistant_artifact(artifact.id)

    routine = get_routine(repo, "routine-catalog")
    assignments = list_routine_assignments(repo, "routine-catalog")

    assert routine.id == "routine-catalog"
    assert assignments.assignments[0].routine_id == "routine-catalog"
```

- [ ] **Step 2: Run the focused tests and verify the new domain package is missing**

Run:

```bash
cd backend && uv run pytest tests/test_routines_catalog_application.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'app.domains'
```

- [ ] **Step 3: Implement the routines repository protocol, SQLite adapter, and catalog use cases**

Create `backend/app/bootstrap/container.py`:

```python
"""Minimal dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository


@dataclass(frozen=True)
class AppContainer:
    routines_repo: SqliteRoutineRepository = field(default_factory=SqliteRoutineRepository)


def build_container() -> AppContainer:
    return AppContainer()
```

Create `backend/app/domains/routines/application/ports.py`:

```python
"""Repository contracts for routines use cases."""

from __future__ import annotations

from typing import Protocol

from app.models import CardLog, CardOverride, CardTemplate, RoutineAssignment, RoutineSchedule


class RoutineRepository(Protocol):
    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]: ...
    def get_routine(self, routine_id: str) -> RoutineSchedule | None: ...
    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]: ...
    def list_card_templates(self, *, status: str | None = None) -> list[CardTemplate]: ...
    def get_card_template(self, card_id: str) -> CardTemplate | None: ...
    def list_card_overrides_range(self, *, start_date: str, end_date: str) -> list[CardOverride]: ...
    def list_card_logs(self, *, date: str | None = None) -> list[CardLog]: ...
    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]: ...
    def save_card_log(self, log: CardLog) -> None: ...
    def save_routine(self, routine: RoutineSchedule) -> None: ...
    def replace_assignments(self, *, routine_id: str, assignments: list[RoutineAssignment]) -> None: ...
```

Create `backend/app/domains/routines/infra/sqlite_repository.py`:

```python
"""SQLite repository adapter for the routines domain."""

from __future__ import annotations

from app.infra.database import (
    delete_routine_assignments,
    load_card_logs,
    load_card_logs_range,
    load_card_overrides_range,
    load_card_template,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedule,
    load_routine_schedules,
    save_card_log,
    save_routine_assignment,
    save_routine_schedule,
)
from app.models import CardLog, RoutineAssignment, RoutineSchedule


class SqliteRoutineRepository:
    def list_routines(self, *, status: str | None = None):
        return load_routine_schedules(status=status)

    def get_routine(self, routine_id: str):
        return load_routine_schedule(routine_id)

    def list_assignments(self, *, routine_id: str | None = None):
        return load_routine_assignments(routine_id=routine_id)

    def list_card_templates(self, *, status: str | None = None):
        return load_card_templates(status=status)

    def get_card_template(self, card_id: str):
        return load_card_template(card_id)

    def list_card_overrides_range(self, *, start_date: str, end_date: str):
        return load_card_overrides_range(start_date, end_date)

    def list_card_logs(self, *, date: str | None = None):
        return load_card_logs(date)

    def list_card_logs_range(self, *, start_date: str, end_date: str):
        return load_card_logs_range(start_date, end_date)

    def save_card_log(self, log: CardLog) -> None:
        save_card_log(log)

    def save_routine(self, routine: RoutineSchedule) -> None:
        save_routine_schedule(routine)

    def replace_assignments(self, *, routine_id: str, assignments: list[RoutineAssignment]) -> None:
        delete_routine_assignments(routine_id)
        for assignment in assignments:
            save_routine_assignment(assignment)
```

Create `backend/app/domains/routines/application/catalog.py`:

```python
"""Catalog use cases for routines."""

from __future__ import annotations

from app.models import RoutineAssignmentsResponse, RoutineSchedule, RoutineSchedulesResponse

from .ports import RoutineRepository


def list_routines(repo: RoutineRepository, status: str | None = None) -> RoutineSchedulesResponse:
    return RoutineSchedulesResponse(routines=repo.list_routines(status=status))


def get_routine(repo: RoutineRepository, routine_id: str) -> RoutineSchedule:
    routine = repo.get_routine(routine_id)
    if routine is None:
        raise LookupError(f"Routine {routine_id} not found")
    return routine


def list_routine_assignments(repo: RoutineRepository, routine_id: str) -> RoutineAssignmentsResponse:
    get_routine(repo, routine_id)
    return RoutineAssignmentsResponse(assignments=repo.list_assignments(routine_id=routine_id))
```

- [ ] **Step 4: Run the catalog tests**

Run:

```bash
cd backend && uv run pytest tests/test_routines_catalog_application.py -v
```

Expected:

```text
tests/test_routines_catalog_application.py::test_list_routines_reads_live_schedules PASSED
tests/test_routines_catalog_application.py::test_get_routine_and_assignments_read_same_routine PASSED
```

- [ ] **Step 5: Commit the routines catalog scaffold**

Run:

```bash
git add backend/app/bootstrap/container.py backend/app/domains backend/tests/test_routines_catalog_application.py
git commit -m "refactor: add routines domain scaffold"
```

## Task 3: Move Schedule Projection Into The Routines Domain

**Files:**
- Create: `backend/app/domains/routines/domain/__init__.py`
- Create: `backend/app/domains/routines/domain/schedule.py`
- Create: `backend/app/domains/routines/application/schedule_window.py`
- Modify: `backend/app/services/schedule_projection.py`
- Test: `backend/tests/test_routines_schedule_application.py`

- [ ] **Step 1: Write the failing schedule-window use-case tests**

Create `backend/tests/test_routines_schedule_application.py`:

```python
"""Routines schedule-window application tests."""

import pytest

from app.domains.routines.application.schedule_window import get_schedule_window
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import save_card_override
from app.models import AssistantArtifactCreateRequest, CardOverride
from app.services.training_specs import activate_assistant_artifact, create_assistant_artifact


def _card_request(card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": "timer_session",
            "slot_default": "evening",
            "summary": "Schedule fixture card",
            "tags": ["training"],
            "payload": {"duration_minutes": 10, "pattern": "5s in / 5s out", "instructions": "Stay relaxed."},
        },
    )


def _routine_request(routine_id: str, *, card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Schedule fixture routine",
            "assignments": [
                {
                    "id": f"{routine_id}-morning-late",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "morning",
                    "position": 30,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def _activate_card(card_id: str) -> None:
    artifact = create_assistant_artifact(_card_request(card_id))
    activate_assistant_artifact(artifact.id)


def _activate_routine(routine_id: str, *, card_id: str) -> None:
    artifact = create_assistant_artifact(_routine_request(routine_id, card_id=card_id))
    activate_assistant_artifact(artifact.id)


def test_schedule_window_returns_sorted_occurrences():
    _activate_card("card-schedule")
    _activate_routine("routine-schedule", card_id="card-schedule")

    repo = SqliteRoutineRepository()
    window = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)

    assert window.start_date == "2026-03-02"
    assert window.end_date == "2026-03-02"
    assert [occurrence.card_template_id for occurrence in window.days[0].occurrences] == ["card-schedule"]


def test_schedule_window_applies_persisted_overrides():
    _activate_card("card-main")
    _activate_card("card-extra")
    _activate_routine("routine-main", card_id="card-main")

    repo = SqliteRoutineRepository()
    baseline = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)
    scheduled_occurrence = baseline.days[0].occurrences[0]
    save_card_override(
        CardOverride(
            id="override-extra",
            date="2026-03-02",
            action="replace",
            target_occurrence_key=scheduled_occurrence.occurrence_key,
            card_template_id="card-extra",
        )
    )
    window = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)

    assert [occurrence.card_template_id for occurrence in window.days[0].occurrences] == ["card-extra"]


def test_schedule_window_rejects_non_positive_duration():
    repo = SqliteRoutineRepository()

    with pytest.raises(ValueError, match="duration_days must be greater than 0"):
        get_schedule_window(repo, start_date="2026-03-02", duration_days=0)
```

- [ ] **Step 2: Run the new schedule-window tests and verify the missing module error**

Run:

```bash
cd backend && uv run pytest tests/test_routines_schedule_application.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'app.domains.routines.application.schedule_window'
```

- [ ] **Step 3: Implement the routines schedule helpers and compatibility wrapper**

Create `backend/app/domains/routines/domain/schedule.py`:

```python
"""Pure schedule-domain helpers."""

from __future__ import annotations

from datetime import date as date_cls

from app.models import CardOverride, CardTemplate, RoutineAssignment, RoutineSchedule, ScheduleOccurrence

SLOT_ORDER = ("morning", "midday", "evening", "anytime")
_SLOT_INDEX = {slot: index for index, slot in enumerate(SLOT_ORDER)}


def parse_schedule_date(date_str: str) -> date_cls:
    return date_cls.fromisoformat(date_str)


def scheduled_occurrence_key(assignment_id: str, date: str) -> str:
    return f"scheduled:{assignment_id}:{date}"


def override_occurrence_key(override: CardOverride, date: str) -> str:
    return f"override:{override.action}:{override.id}:{date}"


def merge_schedule_payload(card: CardTemplate, assignment: RoutineAssignment | None) -> dict[str, object]:
    payload = dict(card.payload_json)
    if assignment is not None and assignment.prescription_override_json:
        payload.update(assignment.prescription_override_json)
    return payload


def routine_is_active_on_date(routine: RoutineSchedule, day: date_cls) -> bool:
    start_date = parse_schedule_date(routine.start_date)
    if day < start_date:
        return False
    if routine.end_date is not None and day > parse_schedule_date(routine.end_date):
        return False
    return routine.status == "active"


def assignment_matches_date(assignment: RoutineAssignment, day: date_cls) -> bool:
    return assignment.date == day.isoformat()


def occurrence_sort_key(occurrence: ScheduleOccurrence) -> tuple[int, int, str]:
    return (_SLOT_INDEX[occurrence.slot], occurrence.position, occurrence.name)
```

Create `backend/app/domains/routines/application/schedule_window.py` by moving the current projection logic out of `backend/app/services/schedule_projection.py` and replacing direct database calls with repository methods:

```python
"""Schedule projection use case for routines."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from app.models import CardOverride, ScheduleDay, ScheduleOccurrence, ScheduleWindow

from app.domains.routines.domain.schedule import (
    assignment_matches_date,
    merge_schedule_payload,
    occurrence_sort_key,
    override_occurrence_key,
    parse_schedule_date,
    routine_is_active_on_date,
    scheduled_occurrence_key,
)

from .ports import RoutineRepository


def _base_occurrences_for_day(day, *, routines, card_lookup, assignments_by_routine):
    occurrences: list[ScheduleOccurrence] = []
    date_str = day.isoformat()
    for routine in routines:
        if not routine_is_active_on_date(routine, day):
            continue
        for assignment in assignments_by_routine.get(routine.id, []):
            if not assignment_matches_date(assignment, day):
                continue
            card = card_lookup.get(assignment.card_template_id)
            if card is None:
                continue
            occurrences.append(
                ScheduleOccurrence(
                    occurrence_key=scheduled_occurrence_key(assignment.id, date_str),
                    date=date_str,
                    slot=assignment.slot,
                    position=assignment.position,
                    source_kind="scheduled",
                    routine_id=routine.id,
                    routine_name=routine.name,
                    assignment_id=assignment.id,
                    card_template_id=card.id,
                    name=card.name,
                    renderer=card.renderer,
                    summary=card.summary,
                    tags=card.tags,
                    payload_json=merge_schedule_payload(card, assignment),
                )
            )
    return occurrences


def _apply_overrides(repo, occurrences, *, date: str, card_lookup, overrides: list[CardOverride]):
    updated = {occurrence.occurrence_key: occurrence for occurrence in occurrences}
    for override in overrides:
        target_occurrence = updated.get(override.target_occurrence_key or "")
        if override.action == "hide":
            if override.target_occurrence_key is not None:
                updated.pop(override.target_occurrence_key, None)
            continue

        if override.card_template_id is None:
            continue
        template = card_lookup.get(override.card_template_id)
        if template is None:
            template = repo.get_card_template(override.card_template_id)
            if template is not None:
                card_lookup[override.card_template_id] = template
        if template is None:
            continue

        slot = override.slot or (target_occurrence.slot if target_occurrence is not None else template.slot_default)
        position = override.position if override.position is not None else (
            target_occurrence.position if target_occurrence is not None else 999
        )
        occurrence = ScheduleOccurrence(
            occurrence_key=override_occurrence_key(override, date),
            date=date,
            slot=slot,
            position=position,
            source_kind=f"override_{override.action}",
            schedule_override_action=override.action,
            target_occurrence_key=override.target_occurrence_key,
            routine_id=target_occurrence.routine_id if target_occurrence is not None else None,
            routine_name=target_occurrence.routine_name if target_occurrence is not None else None,
            assignment_id=target_occurrence.assignment_id if target_occurrence is not None else None,
            card_template_id=template.id,
            name=template.name,
            renderer=template.renderer,
            summary=template.summary,
            tags=template.tags,
            payload_json=dict(template.payload_json),
        )
        if override.action == "replace" and override.target_occurrence_key is not None:
            updated.pop(override.target_occurrence_key, None)
        updated[occurrence.occurrence_key] = occurrence
    return sorted(updated.values(), key=occurrence_sort_key)


def get_schedule_window(repo: RoutineRepository, *, start_date: str, duration_days: int = 14) -> ScheduleWindow:
    if duration_days <= 0:
        raise ValueError("duration_days must be greater than 0")

    window_start = parse_schedule_date(start_date)
    window_end = window_start + timedelta(days=duration_days - 1)
    routines = repo.list_routines(status="active")
    assignments = repo.list_assignments()
    card_lookup = {card.id: card for card in repo.list_card_templates(status="active")}
    assignments_by_routine: dict[str, list] = defaultdict(list)
    for assignment in assignments:
        assignments_by_routine[assignment.routine_id].append(assignment)

    overrides_by_date: dict[str, list] = defaultdict(list)
    for override in repo.list_card_overrides_range(start_date=start_date, end_date=window_end.isoformat()):
        overrides_by_date[override.date].append(override)

    days: list[ScheduleDay] = []
    for offset in range(duration_days):
        day = window_start + timedelta(days=offset)
        date_str = day.isoformat()
        base_occurrences = _base_occurrences_for_day(
            day,
            routines=routines,
            card_lookup=card_lookup,
            assignments_by_routine=assignments_by_routine,
        )
        occurrences = _apply_overrides(
            repo,
            base_occurrences,
            date=date_str,
            card_lookup=card_lookup,
            overrides=overrides_by_date.get(date_str, []),
        )
        days.append(ScheduleDay(date=date_str, occurrences=sorted(occurrences, key=occurrence_sort_key)))

    return ScheduleWindow(start_date=start_date, end_date=window_end.isoformat(), days=days)
```

Replace `backend/app/services/schedule_projection.py` with a compatibility wrapper:

```python
"""Compatibility wrapper for routines schedule projection."""

from app.bootstrap.container import build_container
from app.domains.routines.application.schedule_window import get_schedule_window as _get_schedule_window
from app.domains.routines.domain.schedule import (
    SLOT_ORDER as _SLOT_ORDER,
    override_occurrence_key,
    parse_schedule_date,
    scheduled_occurrence_key,
)

_repo = build_container().routines_repo


def get_schedule_window(start_date: str, duration_days: int = 14):
    return _get_schedule_window(_repo, start_date=start_date, duration_days=duration_days)
```

- [ ] **Step 4: Run both the new application tests and the legacy compatibility tests**

Run:

```bash
cd backend && uv run pytest tests/test_routines_schedule_application.py tests/test_schedule_projection.py -v
```

Expected:

```text
tests/test_routines_schedule_application.py::test_schedule_window_returns_sorted_occurrences PASSED
tests/test_schedule_projection.py::TestScheduleProjection::test_persisted_replace_override_is_applied_to_schedule_window PASSED
```

- [ ] **Step 5: Commit the schedule-window migration**

Run:

```bash
git add backend/app/domains/routines/domain backend/app/domains/routines/application/schedule_window.py backend/app/services/schedule_projection.py backend/tests/test_routines_schedule_application.py
git commit -m "refactor: migrate routines schedule projection"
```

## Task 4: Move Today Read/Write Use Cases Into The Routines Domain

**Files:**
- Create: `backend/app/domains/routines/application/today.py`
- Modify: `backend/app/domains/routines/application/ports.py`
- Modify: `backend/app/services/today.py`
- Test: `backend/tests/test_routines_today_application.py`

- [ ] **Step 1: Write the failing today-use-case tests**

Create `backend/tests/test_routines_today_application.py`:

```python
"""Tests for routines today use cases."""

import pytest

from app.domains.routines.application.today import get_card_log_range, get_today, upsert_today_card_log
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.models import AssistantArtifactCreateRequest, TodayCardLogUpdateRequest
from app.services.training_specs import activate_assistant_artifact, create_assistant_artifact


def _card_request(card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": "timer_session",
            "slot_default": "evening",
            "summary": "Today fixture card",
            "tags": ["training"],
            "payload": {"duration_minutes": 10, "pattern": "5s in / 5s out", "instructions": "Stay relaxed."},
        },
    )


def _routine_request(routine_id: str, *, card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Today fixture routine",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "evening",
                    "position": 20,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def test_get_today_returns_grouped_slots_and_stats():
    card_artifact = create_assistant_artifact(_card_request("card-today"))
    activate_assistant_artifact(card_artifact.id)
    routine_artifact = create_assistant_artifact(_routine_request("routine-today", card_id="card-today"))
    activate_assistant_artifact(routine_artifact.id)

    repo = SqliteRoutineRepository()
    response = get_today(repo, date="2026-03-02")

    assert response.date == "2026-03-02"
    assert response.stats.total == 1
    assert response.slots[2].cards[0].card_template_id == "card-today"


def test_get_card_log_range_excludes_pending_entries():
    repo = SqliteRoutineRepository()
    response = get_card_log_range(repo, start_date="2026-03-02", end_date="2026-03-02")
    assert response.entries == []


def test_upsert_today_card_log_validates_occurrence_identity():
    repo = SqliteRoutineRepository()
    request = TodayCardLogUpdateRequest(
        card_template_id="wrong-card",
        assignment_id=None,
        status="completed",
        actual_json={},
        notes=None,
    )

    with pytest.raises(LookupError, match="Today occurrence missing not found"):
        upsert_today_card_log(repo, date="2026-03-02", occurrence_key="missing", request=request)
```

- [ ] **Step 2: Run the today tests and verify the module import failure**

Run:

```bash
cd backend && uv run pytest tests/test_routines_today_application.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'app.domains.routines.application.today'
```

- [ ] **Step 3: Implement today reads/writes and keep the flat service as a wrapper**

Expand `backend/app/domains/routines/application/today.py`:

```python
"""Today board use cases for routines."""

from __future__ import annotations

from collections import defaultdict

from app.models import (
    CardLog,
    CardLogRangeResponse,
    CardLogStatusEntry,
    TodayCard,
    TodayCardLogUpdateRequest,
    TodayResponse,
    TodaySlot,
    TodayStats,
)

from app.domains.routines.domain.schedule import SLOT_ORDER
from app.domains.routines.application.schedule_window import get_schedule_window

from .ports import RoutineRepository

_SLOT_LABELS = {
    "morning": "Morning",
    "midday": "Midday",
    "evening": "Evening",
    "anytime": "Anytime",
}


def get_card_log_range(repo: RoutineRepository, *, start_date: str, end_date: str) -> CardLogRangeResponse:
    logs = repo.list_card_logs_range(start_date=start_date, end_date=end_date)
    entries = [
        CardLogStatusEntry(occurrence_key=log.occurrence_key, status=log.status)
        for log in logs
        if log.status != "pending"
    ]
    return CardLogRangeResponse(start_date=start_date, end_date=end_date, entries=entries)


def get_today(repo: RoutineRepository, *, date: str) -> TodayResponse:
    window = get_schedule_window(repo, start_date=date, duration_days=1)
    occurrences = window.days[0].occurrences if window.days else []
    cards = {occurrence.occurrence_key: TodayCard(**occurrence.model_dump()) for occurrence in occurrences}

    logs_by_occurrence = {log.occurrence_key: log for log in repo.list_card_logs(date=date)}
    for occurrence_key, card in cards.items():
        log = logs_by_occurrence.get(occurrence_key)
        if log is None:
            continue
        card.status = log.status
        card.actual_json = log.actual_json
        card.notes = log.notes

    grouped: dict[str, list[TodayCard]] = defaultdict(list)
    for card in cards.values():
        grouped[card.slot].append(card)

    slots: list[TodaySlot] = []
    stats = TodayStats()
    for slot in SLOT_ORDER:
        slot_cards = sorted(grouped.get(slot, []), key=lambda card: (card.position, card.name))
        slots.append(TodaySlot(slot=slot, label=_SLOT_LABELS[slot], cards=slot_cards))
        for card in slot_cards:
            stats.total += 1
            if card.status == "completed":
                stats.completed += 1
            elif card.status == "partial":
                stats.partial += 1
            elif card.status == "skipped":
                stats.skipped += 1
            else:
                stats.pending += 1

    return TodayResponse(date=date, stats=stats, slots=slots)


def upsert_today_card_log(repo: RoutineRepository, *, date: str, occurrence_key: str, request: TodayCardLogUpdateRequest) -> CardLog:
    scheduled_cards = {card.occurrence_key: card for slot in get_today(repo, date=date).slots for card in slot.cards}
    scheduled_card = scheduled_cards.get(occurrence_key)
    if scheduled_card is None:
        raise LookupError(f"Today occurrence {occurrence_key} not found for {date}")
    if request.card_template_id != scheduled_card.card_template_id:
        raise ValueError("Card template does not match the scheduled occurrence")
    if request.assignment_id is not None and request.assignment_id != scheduled_card.assignment_id:
        raise ValueError("Assignment id does not match the scheduled occurrence")

    log = CardLog(
        id=f"card-log:{date}:{occurrence_key}",
        date=date,
        occurrence_key=occurrence_key,
        card_template_id=scheduled_card.card_template_id,
        assignment_id=scheduled_card.assignment_id,
        status=request.status,
        actual_json=request.actual_json,
        notes=request.notes,
    )
    repo.save_card_log(log)
    return log
```

Replace `backend/app/services/today.py` with:

```python
"""Compatibility wrapper for routines today use cases."""

from app.bootstrap.container import build_container
from app.domains.routines.application.today import (
    get_card_log_range,
    get_today as _get_today,
    upsert_today_card_log as _upsert_today_card_log,
)

_repo = build_container().routines_repo


def get_today(date: str):
    return _get_today(_repo, date=date)


def upsert_today_card_log(date: str, occurrence_key: str, request):
    return _upsert_today_card_log(_repo, date=date, occurrence_key=occurrence_key, request=request)
```

- [ ] **Step 4: Run the new tests and the existing today/runtime compatibility coverage**

Run:

```bash
cd backend && uv run pytest tests/test_routines_today_application.py tests/test_training_specs.py tests/test_training_routes.py -v
```

Expected:

```text
tests/test_routines_today_application.py::test_get_today_returns_grouped_slots_and_stats PASSED
tests/test_training_specs.py::TestCompiledTrainingRuntime::test_today_matches_schedule_projection_when_overrides_exist PASSED
tests/test_training_routes.py::TestTodayRoutes::test_delete_today_card_returns_405 PASSED
```

- [ ] **Step 5: Commit the today migration**

Run:

```bash
git add backend/app/domains/routines/application/today.py backend/app/domains/routines/application/ports.py backend/app/services/today.py backend/tests/test_routines_today_application.py
git commit -m "refactor: migrate routines today use cases"
```

## Task 5: Move Routine Activation And Routes Into Domain Packages

**Files:**
- Create: `backend/app/domains/routines/api/__init__.py`
- Create: `backend/app/domains/routines/api/routines.py`
- Create: `backend/app/domains/routines/api/today.py`
- Create: `backend/app/domains/routines/application/activation.py`
- Modify: `backend/app/bootstrap/routing.py`
- Modify: `backend/app/routers/routines.py`
- Modify: `backend/app/routers/today.py`
- Modify: `backend/app/services/training_specs.py`
- Modify: `backend/tests/test_main.py`
- Test: `backend/tests/test_routines_activation_application.py`

- [ ] **Step 1: Write the failing routine-activation and route-wiring tests**

Create `backend/tests/test_routines_activation_application.py`:

```python
"""Routine artifact compilation tests for the routines domain."""

from app.domains.routines.application.activation import compile_routine_artifact
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import load_routine_assignments, load_routine_schedule
from app.models import AssistantArtifact


def test_compile_routine_artifact_persists_schedule_and_assignments():
    repo = SqliteRoutineRepository()
    artifact = AssistantArtifact(
        id="artifact-routine-activation",
        kind="routine_spec",
        schema_version=1,
        status="validated",
        payload_json={
            "id": "routine-activation",
            "name": "Routine Activation",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Activation fixture",
            "assignments": [
                {
                    "id": "assignment-activation",
                    "card_template_id": "card-activation",
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                }
            ],
        },
        validation_errors=[],
        created_at="2026-03-01T00:00:00Z",
        updated_at="2026-03-01T00:00:00Z",
    )

    compile_routine_artifact(
        repo,
        artifact,
        activate_card_template_dependency=lambda *_args, **_kwargs: None,
    )

    assert load_routine_schedule("routine-activation") is not None
    assert load_routine_assignments(routine_id="routine-activation")[0].id == "assignment-activation"
```

Update `backend/tests/test_main.py` route monkeypatch target:

```python
monkeypatch.setattr(
    "app.domains.routines.api.routines.get_schedule_window",
    lambda *_args: (_ for _ in ()).throw(ValueError("duration_days must be > 0")),
)
```

- [ ] **Step 2: Run the focused tests and verify the activation module is missing**

Run:

```bash
cd backend && uv run pytest tests/test_routines_activation_application.py tests/test_main.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'app.domains.routines.application.activation'
```

- [ ] **Step 3: Implement domain-local routes, activation logic, and compatibility wrappers**

Create `backend/app/domains/routines/application/activation.py`:

```python
"""Routine activation use case."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from app.models import AssistantArtifact, RoutineAssignment, RoutineSchedule, RoutineSpec

from .ports import RoutineRepository


def compile_routine_artifact(
    repo: RoutineRepository,
    artifact: AssistantArtifact,
    *,
    activate_card_template_dependency: Callable[[str, AssistantArtifact | None], None],
) -> RoutineSchedule:
    spec = RoutineSpec.model_validate(artifact.payload_json)
    for assignment in spec.assignments:
        activate_card_template_dependency(assignment.card_template_id, artifact)

    routine = RoutineSchedule(
        id=spec.id,
        name=spec.name,
        status=spec.status,
        start_date=spec.start_date,
        end_date=spec.end_date,
        tags=spec.tags,
        notes=spec.notes,
        source_artifact_id=artifact.id,
    )
    repo.save_routine(routine)

    start = date.fromisoformat(spec.start_date)
    compiled_assignments = [
        RoutineAssignment(
            id=assignment.id,
            routine_id=routine.id,
            card_template_id=assignment.card_template_id,
            date=(start + timedelta(days=assignment.day - 1)).isoformat(),
            slot=assignment.slot,
            position=assignment.position,
            prescription_override_json=assignment.prescription_override_json,
        )
        for assignment in spec.assignments
    ]
    repo.replace_assignments(routine_id=routine.id, assignments=compiled_assignments)
    return routine
```

Create `backend/app/domains/routines/api/routines.py`:

```python
"""Domain-local routines routes."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.routines.application.catalog import get_routine, list_routine_assignments, list_routines
from app.domains.routines.application.schedule_window import get_schedule_window
from app.models import RoutineAssignmentsResponse, RoutineSchedule, RoutineSchedulesResponse, ScheduleWindow

router = APIRouter(prefix="/api/routines", tags=["routines"])
_repo = build_container().routines_repo


@router.get("", response_model=RoutineSchedulesResponse)
def get_routines(status: str | None = None):
    return list_routines(_repo, status=status)


@router.get("/schedule-window", response_model=ScheduleWindow)
def get_routine_schedule_window(start_date: str = Query(..., description="Start date for the 14-day schedule window")):
    return get_schedule_window(_repo, start_date=start_date)


@router.get("/{routine_id}", response_model=RoutineSchedule)
def get_routine_detail(routine_id: str):
    return get_routine(_repo, routine_id)


@router.get("/{routine_id}/assignments", response_model=RoutineAssignmentsResponse)
def get_assignments(routine_id: str):
    return list_routine_assignments(_repo, routine_id)
```

Create `backend/app/domains/routines/api/today.py`:

```python
"""Domain-local today routes."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.routines.application.today import get_card_log_range, get_today, upsert_today_card_log
from app.models import CardLog, CardLogRangeResponse, TodayCardLogUpdateRequest, TodayResponse

router = APIRouter(prefix="/api/today", tags=["today"])
_repo = build_container().routines_repo


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    return get_today(_repo, date=date)


@router.get("/card-logs", response_model=CardLogRangeResponse)
def get_today_card_logs(start_date: str = Query(...), end_date: str = Query(...)):
    return get_card_log_range(_repo, start_date=start_date, end_date=end_date)


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    return upsert_today_card_log(_repo, date=date, occurrence_key=occurrence_key, request=request)
```

Update `backend/app/services/training_specs.py` to delegate routines behavior:

```python
from app.bootstrap.container import build_container
from app.domains.routines.application.activation import compile_routine_artifact
from app.domains.routines.application.catalog import (
    get_routine as get_domain_routine,
    list_routine_assignments as list_domain_routine_assignments,
    list_routines as list_domain_routines,
)

_routine_repo = build_container().routines_repo


def _compile_routine_spec_artifact(artifact: AssistantArtifact) -> RoutineSchedule:
    return compile_routine_artifact(
        _routine_repo,
        artifact,
        activate_card_template_dependency=_activate_card_template_dependency,
    )


def list_routines(status: str | None = None) -> RoutineSchedulesResponse:
    return list_domain_routines(_routine_repo, status=status)


def get_routine(routine_id: str) -> RoutineSchedule:
    return get_domain_routine(_routine_repo, routine_id)


def list_routine_assignments(routine_id: str) -> RoutineAssignmentsResponse:
    return list_domain_routine_assignments(_routine_repo, routine_id)
```

Replace `backend/app/routers/routines.py` with:

```python
"""Compatibility wrapper for routines routes."""

from app.domains.routines.api.routines import (
    get_assignments,
    get_routine_detail,
    get_routine_schedule_window,
    get_routines,
    router,
)

__all__ = [
    "router",
    "get_routines",
    "get_routine_schedule_window",
    "get_routine_detail",
    "get_assignments",
]
```

Replace `backend/app/routers/today.py` with:

```python
"""Compatibility wrapper for today routes."""

from app.domains.routines.api.today import (
    get_today_card_logs,
    get_today_view,
    put_today_card_log,
    router,
)

__all__ = [
    "router",
    "get_today_view",
    "get_today_card_logs",
    "put_today_card_log",
]
```

Finally, update `backend/app/bootstrap/routing.py` so the app includes domain-local routers for routines/today:

```python
from app.domains.routines.api.routines import router as routines_router
from app.domains.routines.api.today import router as today_router
```

- [ ] **Step 4: Run the activation, route, and compatibility tests**

Run:

```bash
cd backend && uv run pytest tests/test_routines_activation_application.py tests/test_main.py tests/test_training_specs.py tests/test_training_routes.py -v
```

Expected:

```text
tests/test_routines_activation_application.py::test_compile_routine_artifact_persists_schedule_and_assignments PASSED
tests/test_main.py::TestExceptionHandlers::test_value_error_returns_400 PASSED
tests/test_training_specs.py::TestAssistantArtifactActivation::test_routine_artifact_compiles_live_schedule PASSED
```

- [ ] **Step 5: Commit the routines API and activation migration**

Run:

```bash
git add backend/app/domains/routines/api backend/app/domains/routines/application/activation.py backend/app/routers/routines.py backend/app/routers/today.py backend/app/services/training_specs.py backend/app/bootstrap/routing.py backend/tests/test_routines_activation_application.py backend/tests/test_main.py
git commit -m "refactor: move routines routes and activation into domain"
```

## Task 6: Add Boundary Guards And Run Full Backend Verification

**Files:**
- Create: `backend/tests/test_architecture_routines_boundaries.py`
- Modify: `backend/tests/test_training_specs.py`

- [ ] **Step 1: Write the failing architecture-guard tests**

Create `backend/tests/test_architecture_routines_boundaries.py`:

```python
"""Architecture guard rails for the routines domain slice."""

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_routines_api_modules_do_not_import_flat_database_or_services():
    for path in [
        "backend/app/domains/routines/api/routines.py",
        "backend/app/domains/routines/api/today.py",
    ]:
        source = _read(path)
        assert "app.infra.database" not in source
        assert "app.services." not in source


def test_routines_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/routines/application/catalog.py",
        "backend/app/domains/routines/application/schedule_window.py",
        "backend/app/domains/routines/application/today.py",
        "backend/app/domains/routines/application/activation.py",
    ]:
        assert "fastapi" not in _read(path)


def test_flat_routines_routers_are_compatibility_wrappers():
    source = _read("backend/app/routers/routines.py")
    assert "domains.routines.api.routines" in source
    assert "APIRouter(" not in source
```

- [ ] **Step 2: Run the architecture tests and fix any remaining illegal imports**

Run:

```bash
cd backend && uv run pytest tests/test_architecture_routines_boundaries.py -v
```

Expected:

```text
tests/test_architecture_routines_boundaries.py::test_routines_api_modules_do_not_import_flat_database_or_services PASSED
tests/test_architecture_routines_boundaries.py::test_routines_application_modules_are_fastapi_free PASSED
tests/test_architecture_routines_boundaries.py::test_flat_routines_routers_are_compatibility_wrappers PASSED
```

- [ ] **Step 3: Make the routines slice pass the guard rails**

If any guard fails, fix the offending imports so the routines slice keeps these exact dependency directions:

```python
# Good: API module imports application layer only
from app.bootstrap.container import build_container
from app.domains.routines.application.today import get_card_log_range, get_today, upsert_today_card_log

# Good: application layer imports models + domain helpers + repository protocol only
from app.models import TodayResponse
from app.domains.routines.domain.schedule import SLOT_ORDER
from .ports import RoutineRepository
```

- [ ] **Step 4: Run the required backend verification commands**

Run:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

Expected:

```text
All checks pass with 0 ruff errors, 0 pyright errors, and a fully passing backend test suite.
```

- [ ] **Step 5: Commit the guard rails and the verified slice**

Run:

```bash
git add backend/tests/test_architecture_routines_boundaries.py backend/tests/test_training_specs.py
git commit -m "test: enforce routines slice boundaries"
```

## Self-Review Checklist

### Spec coverage

This plan covers the approved spec's first milestone only:

- bootstrap split from `main.py`: Task 1
- initial shared core extraction: Task 1 (`backend/app/core/config.py`)
- routines domain package skeleton: Task 2
- routines vertical migration: Tasks 3, 4, 5
- compatibility seams: Tasks 3, 4, 5
- enforcement after seams exist: Task 6
- backend verification: Task 6

### Placeholder scan

Search before execution:

```bash
rg -n "TODO|TBD|implement later|appropriate error handling|similar to task" docs/superpowers/plans/2026-04-08-backend-bootstrap-and-routines-slice.md | rg -v "rg -n"
```

Expected:

```text
(no output)
```

### Type consistency

Keep these names consistent across all tasks:

- repository protocol: `RoutineRepository`
- repo adapter: `SqliteRoutineRepository`
- schedule use case: `get_schedule_window`
- today use cases: `get_today`, `get_card_log_range`, `upsert_today_card_log`
- activation use case: `compile_routine_artifact`
- bootstrap entrypoint: `create_app`

If any later task introduces a different name, rename it to match this plan before writing code.
