# Programs Structural Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flatten the `domains/programs` backend slice to match routines and experiments while preserving current program API and persistence behavior.

**Architecture:** Programs keeps contracts in `contracts.py` and use cases in `application/programs.py`. FastAPI routing moves to root-level `routes.py`, dependency protocols move to root-level `dependencies.py`, and SQLite persistence moves to root-level `adapters.py`. Shared SQLite schema creation stays in `app.infra.database`, but program CRUD/version helpers leave that shared bucket.

**Tech Stack:** Python 3.14, FastAPI, Pydantic contracts, SQLite, project `JsonStore`, pytest architecture guards, ruff, pyright.

---

## File Structure

- `backend/app/domains/programs/routes.py`
  Owns `/api/programs` FastAPI route handlers and container dependency lookup.
- `backend/app/domains/programs/dependencies.py`
  Owns the `ProgramRepository` protocol consumed by program use cases.
- `backend/app/domains/programs/adapters.py`
  Owns `SqliteProgramRepository` plus program-specific SQLite load/save helpers.
- `backend/app/domains/programs/application/programs.py`
  Keeps program import/list/read/activate/retire/version use cases unchanged except for the dependency import path.
- `backend/app/bootstrap/routing.py`
  Imports the programs router from the flattened module.
- `backend/app/bootstrap/container.py`
  Imports the SQLite program repository from the flattened adapter module.
- `backend/app/infra/database.py`
  Keeps program table schema creation but loses program contract imports and program CRUD/version helper functions.
- `backend/tests/architecture/test_architecture_programs_boundaries.py`
  Guards the new layout and database ownership boundary.
- `backend/tests/architecture/test_architecture_global_ownership.py`
  Removes programs from the allowlist of shared database importers.
- `backend/tests/domains/programs/test_programs_service.py`
  Imports the repository adapter from `domains.programs.adapters`.
- `docs/ARCHITECTURE.md`
  Documents the flattened programs layout.

---

### Task 1: Write The Failing Architecture Guards

**Files:**
- Modify: `backend/tests/architecture/test_architecture_programs_boundaries.py`
- Modify: `backend/tests/architecture/test_architecture_global_ownership.py`

- [ ] **Step 1: Replace the programs boundary test with flattened-layout expectations**

Replace `backend/tests/architecture/test_architecture_programs_boundaries.py` with:

```python
"""Architecture guard rails for the programs domain slice."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    assert_no_text_in_files,
    read_repo_file,
)


def test_programs_route_module_does_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/programs/routes.py",
    ])


def test_programs_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/programs/dependencies.py",
        "backend/app/domains/programs/application/programs.py",
    ])


def test_programs_uses_flat_capability_layout():
    for path in [
        "backend/app/domains/programs/api",
        "backend/app/domains/programs/infra",
        "backend/app/domains/programs/application/ports.py",
    ]:
        assert not (REPO_ROOT / path).exists()

    for path in [
        "backend/app/domains/programs/routes.py",
        "backend/app/domains/programs/adapters.py",
        "backend/app/domains/programs/dependencies.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_programs_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/programs/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteProgramRepository" in source
    assert "def save_program_import(" in source


def test_programs_routes_use_container_repository():
    source = read_repo_file("backend/app/domains/programs/routes.py")
    assert "build_container" in source
    assert "programs_repo" in source


def test_bootstrap_routing_mounts_domain_programs_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.programs.routes" in source
    assert "domains.programs.api.programs" not in source
    assert "from ..routers.programs import router as programs_router" not in source
    assert "include_router(programs_router)" in source


def test_programs_domain_does_not_write_legacy_routine_or_experiment_children():
    assert_no_text_in_files(
        [
            "backend/app/domains/programs/dependencies.py",
            "backend/app/domains/programs/application/programs.py",
            "backend/app/domains/programs/adapters.py",
        ],
        [
            "Routine",
            "Experiment",
            "replace_program_import",
            "_protocol_to_routine",
            "_spec_experiment_to_model",
        ],
    )


def test_shared_database_does_not_own_program_contracts_or_crud():
    source = read_repo_file("backend/app/infra/database.py")
    assert "domains.programs.contracts" not in source

    program_persistence_functions = [
        "def save_program(",
        "def load_program(",
        "def load_programs(",
        "def save_program_version(",
        "def load_program_versions(",
        "def delete_program(",
        "def save_program_import(",
    ]
    assert [name for name in program_persistence_functions if name in source] == []


def test_migrated_programs_service_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/services/programs.py").exists()


def test_migrated_programs_router_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/routers/programs.py").exists()


def test_backend_code_does_not_import_migrated_programs_shims():
    assert_no_repo_imports_of(
        [
            "app.services.programs",
            "app.routers.programs",
            "..services.programs",
            "..routers.programs",
        ],
        Path(__file__),
    )
```

- [ ] **Step 2: Remove programs from the shared database importer allowlist**

In `backend/tests/architecture/test_architecture_global_ownership.py`, replace the database allowlist with:

```python
ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS = {
    "backend/app/core/profile/infra/sqlite_repository.py",
    "backend/app/domains/assistant/infra/sqlite_repository.py",
    "backend/app/domains/experiments/adapters.py",
    "backend/app/domains/journal/infra/sqlite_repository.py",
}
```

- [ ] **Step 3: Run the architecture tests and verify they fail for the intended reasons**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_programs_boundaries.py tests/architecture/test_architecture_global_ownership.py -v
```

Expected: FAIL because `domains/programs/routes.py`, `adapters.py`, and `dependencies.py` do not exist yet, bootstrap still imports `domains.programs.api.programs`, and `app.infra.database` still imports program contracts and owns program CRUD helpers.

- [ ] **Step 4: Commit the failing tests**

```bash
git add backend/tests/architecture/test_architecture_programs_boundaries.py backend/tests/architecture/test_architecture_global_ownership.py
git commit -m "test: lock programs flat boundary expectations"
```

---

### Task 2: Flatten Program Routes And Dependencies

**Files:**
- Create: `backend/app/domains/programs/routes.py`
- Create: `backend/app/domains/programs/dependencies.py`
- Modify: `backend/app/domains/programs/application/programs.py`
- Modify: `backend/app/bootstrap/routing.py`
- Delete: `backend/app/domains/programs/api/programs.py`
- Delete: `backend/app/domains/programs/api/__init__.py`
- Delete: `backend/app/domains/programs/application/ports.py`

- [ ] **Step 1: Create the root-level dependency protocol**

Create `backend/app/domains/programs/dependencies.py`:

```python
"""Dependencies consumed by program application use cases.

Program workflows persist imported specs, lifecycle state, and version history
through this protocol. Concrete SQLite details belong in the adapter layer.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.programs.contracts import (
    Program,
    ProgramStatus,
    ProgramVersion,
)


class ProgramRepository(Protocol):
    """Persistence dependency for program import and lifecycle workflows."""

    def get_program(self, program_id: str) -> Program | None: ...

    def list_programs(self, *, status: ProgramStatus | None = None) -> list[Program]: ...

    def save_program(self, program: Program) -> None: ...

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]: ...

    def save_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
    ) -> None: ...
```

- [ ] **Step 2: Point application use cases at the new dependency module**

In `backend/app/domains/programs/application/programs.py`, replace:

```python
from .ports import ProgramRepository
```

with:

```python
from app.domains.programs.dependencies import ProgramRepository
```

- [ ] **Step 3: Create the root-level routes module**

Create `backend/app/domains/programs/routes.py`:

```python
"""Program spec HTTP routes."""

from fastapi import APIRouter, HTTPException

from app.bootstrap.container import build_container
from app.domains.programs.application.programs import (
    activate_program,
    get_program,
    get_program_versions,
    import_program,
    list_programs,
    retire_program,
)
from app.domains.programs.contracts import (
    Program,
    ProgramsResponse,
    ProgramStatus,
    ProgramVersionsResponse,
)

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("", response_model=ProgramsResponse)
def get_programs(status: ProgramStatus | None = None):
    """Return all programs, optionally filtered by status."""
    return list_programs(build_container().programs_repo, status=status)


@router.get("/{program_id}", response_model=Program)
def get_program_detail(program_id: str):
    """Return a single program with its full spec."""
    try:
        return get_program(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/import", response_model=Program)
def post_import_program(spec: dict[str, object]):
    """Import a placeholder program spec JSON without activating child records."""
    try:
        return import_program(build_container().programs_repo, spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{program_id}/retire", response_model=Program)
def put_retire_program(program_id: str):
    """Set a program's status to retired, preserving all data."""
    try:
        return retire_program(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{program_id}/activate", response_model=Program)
def put_activate_program(program_id: str):
    """Reactivate a retired program."""
    try:
        return activate_program(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{program_id}/versions", response_model=ProgramVersionsResponse)
def get_versions(program_id: str):
    """Return version history for a program."""
    try:
        return get_program_versions(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
```

- [ ] **Step 4: Update bootstrap routing**

In `backend/app/bootstrap/routing.py`, replace:

```python
from app.domains.programs.api.programs import router as programs_router
```

with:

```python
from app.domains.programs.routes import router as programs_router
```

- [ ] **Step 5: Delete the old route and port files**

Delete:

```text
backend/app/domains/programs/api/programs.py
backend/app/domains/programs/api/__init__.py
backend/app/domains/programs/application/ports.py
```

Then remove the now-empty route package directory:

```bash
rmdir backend/app/domains/programs/api
```

- [ ] **Step 6: Run the focused architecture tests**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_programs_boundaries.py -v
```

Expected: FAIL only on the adapter/database-boundary checks and the still-present `domains/programs/infra` package. Route and dependency checks should no longer fail.

- [ ] **Step 7: Commit the route and dependency flattening**

```bash
git add backend/app/domains/programs/routes.py backend/app/domains/programs/dependencies.py backend/app/domains/programs/application/programs.py backend/app/bootstrap/routing.py backend/app/domains/programs/api/programs.py backend/app/domains/programs/api/__init__.py backend/app/domains/programs/application/ports.py
git commit -m "refactor: flatten programs routes and dependencies"
```

---

### Task 3: Move Program Persistence Into The Adapter

**Files:**
- Create: `backend/app/domains/programs/adapters.py`
- Modify: `backend/app/bootstrap/container.py`
- Modify: `backend/app/infra/database.py`
- Modify: `backend/tests/domains/programs/test_programs_service.py`
- Delete: `backend/app/domains/programs/infra/sqlite_repository.py`
- Delete: `backend/app/domains/programs/infra/__init__.py`

- [ ] **Step 1: Create the flattened SQLite adapter with moved persistence helpers**

Create `backend/app/domains/programs/adapters.py`:

```python
"""SQLite-backed program repository adapter.

This module is the persistence boundary for imported program specs and version
history. It owns program-specific CRUD while shared SQLite connection and JSON
record primitives remain in `app.infra`.
"""

from __future__ import annotations

from app.domains.programs.contracts import (
    Program,
    ProgramStatus,
    ProgramVersion,
)
from app.infra.jsonstore import JsonStore
from app.infra.jsonstore import model_from_row as _model_from_row
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({"programs"})


def save_program(program: Program) -> None:
    """Persist the current record for one imported program."""
    _STORE.save("programs", program.id, program.model_dump_json())


def load_program(program_id: str) -> Program | None:
    """Load one imported program by id."""
    return _STORE.load("programs", Program, program_id)


def load_programs(status: ProgramStatus | None = None) -> list[Program]:
    """Load imported programs, optionally filtered by lifecycle status."""
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _STORE.load_many(
        "programs",
        Program,
        where_sql=where_sql,
        params=params,
    )


def load_program_versions(program_id: str) -> list[ProgramVersion]:
    """Load stored prior versions for one program ordered by version number."""
    with connect() as con:
        rows = con.execute(
            "SELECT data, created_at, updated_at FROM program_versions "
            "WHERE program_id = ? ORDER BY version",
            (program_id,),
        ).fetchall()
    return [_model_from_row(ProgramVersion, row) for row in rows]


def save_program_import(
    *,
    program: Program,
    previous_version: ProgramVersion | None,
) -> None:
    """Persist a program import and optional previous version atomically."""
    timestamp = now_iso()
    with connect() as con, con:
        if previous_version is not None:
            con.execute(
                "INSERT OR REPLACE INTO program_versions "
                "(program_id, version, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    previous_version.program_id,
                    previous_version.version,
                    previous_version.model_dump_json(),
                    timestamp,
                    timestamp,
                ),
            )

        _STORE.save_in_connection(
            con,
            "programs",
            program.id,
            program.model_dump_json(),
        )


class SqliteProgramRepository:
    """Repository adapter used by program application use cases."""

    def get_program(self, program_id: str) -> Program | None:
        """Load one program definition by id."""
        return load_program(program_id)

    def list_programs(self, *, status: ProgramStatus | None = None) -> list[Program]:
        """Load programs, optionally filtered by lifecycle status."""
        return load_programs(status=status)

    def save_program(self, program: Program) -> None:
        """Persist one current program record."""
        save_program(program)

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]:
        """Load prior versions for one program."""
        return load_program_versions(program_id)

    def save_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
    ) -> None:
        """Persist an import transaction for the current and previous versions."""
        save_program_import(
            program=program,
            previous_version=previous_version,
        )
```

- [ ] **Step 2: Update the dependency container import**

In `backend/app/bootstrap/container.py`, replace:

```python
from app.domains.programs.infra.sqlite_repository import SqliteProgramRepository
```

with:

```python
from app.domains.programs.adapters import SqliteProgramRepository
```

- [ ] **Step 3: Update program domain tests to import the flattened adapter**

In `backend/tests/domains/programs/test_programs_service.py`, replace:

```python
from app.domains.programs.infra.sqlite_repository import SqliteProgramRepository
```

with:

```python
from app.domains.programs.adapters import SqliteProgramRepository
```

- [ ] **Step 4: Remove program contract imports from shared database**

In `backend/app/infra/database.py`, delete:

```python
from ..domains.programs.contracts import Program, ProgramVersion
```

Also delete this import if no remaining use exists:

```python
from .jsonstore import model_from_row as _model_from_row
```

- [ ] **Step 5: Remove program tables from the shared JsonStore allowlist**

In `backend/app/infra/database.py`, change the end of `_VALID_TABLES` from:

```python
    "assistant_evidence_bundles", "assistant_memory_records",
    "evidence_cards", "programs", "program_versions",
    "assistant_artifacts",
```

to:

```python
    "assistant_evidence_bundles", "assistant_memory_records",
    "evidence_cards", "assistant_artifacts",
```

- [ ] **Step 6: Delete the program storage helper block from shared database**

In `backend/app/infra/database.py`, delete the whole block from:

```python
# ---------------------------------------------------------------------------
# Program storage
# ---------------------------------------------------------------------------
```

through the end of the file, including these functions:

```python
def save_program(program: Program) -> None:
def load_program(program_id: str) -> Program | None:
def load_programs(status: str | None = None) -> list[Program]:
def save_program_version(version: ProgramVersion) -> None:
def load_program_versions(program_id: str) -> list[ProgramVersion]:
def delete_program(program_id: str) -> None:
def save_program_import(
```

- [ ] **Step 7: Delete the old infra adapter files**

Delete:

```text
backend/app/domains/programs/infra/sqlite_repository.py
backend/app/domains/programs/infra/__init__.py
```

Then remove the now-empty infra package directory:

```bash
rmdir backend/app/domains/programs/infra
```

- [ ] **Step 8: Run focused tests for programs and architecture**

Run:

```bash
cd backend && uv run pytest tests/domains/programs/test_programs_service.py tests/architecture/test_architecture_programs_boundaries.py tests/architecture/test_architecture_global_ownership.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit the persistence move**

```bash
git add backend/app/domains/programs/adapters.py backend/app/bootstrap/container.py backend/app/infra/database.py backend/tests/domains/programs/test_programs_service.py backend/app/domains/programs/infra/sqlite_repository.py backend/app/domains/programs/infra/__init__.py
git commit -m "refactor: move programs persistence into adapter"
```

---

### Task 4: Update Architecture Documentation And Check Import Cleanup

**Files:**
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Update the active service area entry for programs**

In `docs/ARCHITECTURE.md`, replace the `domains/programs/` bullet under "Active service areas" with:

```markdown
- `domains/programs/`
  Secondary backend domain for program spec import and management. This domain
  owns `/api/programs`; `routes.py` owns HTTP routes, `application/` owns import,
  activation/retirement, and version use cases, `dependencies.py` owns the
  repository dependency protocol, and `adapters.py` owns SQLite program spec and
  version-history persistence. Program imports currently persist the program
  spec and version history only; protocol, routine, and experiment activation is
  intentionally not implemented yet.
```

- [ ] **Step 2: Check for old programs paths**

Run:

```bash
rg "domains\\.programs\\.(api|infra|application\\.ports)|app\\.domains\\.programs\\.(api|infra|application\\.ports)" backend/app backend/tests docs/ARCHITECTURE.md docs/README.md README.md
```

Expected: no output.

- [ ] **Step 3: Run architecture tests**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_programs_boundaries.py tests/architecture/test_architecture_global_ownership.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit docs and cleanup verification changes**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: document programs flat layout"
```

---

### Task 5: Run Required Backend Validation

**Files:**
- No planned file edits.

- [ ] **Step 1: Run backend lint**

Run:

```bash
cd backend && uv run ruff check
```

Expected: PASS with `All checks passed!`.

- [ ] **Step 2: Run backend type check**

Run:

```bash
cd backend && uv run pyright app/ tests/
```

Expected: PASS with `0 errors`.

- [ ] **Step 3: Run backend tests**

Run:

```bash
cd backend && uv run pytest tests/ -v
```

Expected: PASS.

- [ ] **Step 4: Confirm API types do not need regeneration**

Run:

```bash
git diff -- frontend/src/lib/api-types.ts
```

Expected: no output because this refactor preserves routes, response models, and request bodies.

- [ ] **Step 5: Review final diff**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: only intended programs, bootstrap, architecture-test, and architecture-doc files are changed since the last task commit.
