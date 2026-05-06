# Model Contract Ownership Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start draining `backend/app/models.py` by moving owned Pydantic contracts into the modules that own them while preserving OpenAPI and frontend type stability.

**Architecture:** This plan follows `docs/superpowers/plans/2026-05-06-architecture-boundary-cleanup.md`. The previous plan makes boundaries explicit; this plan uses those boundaries to move contracts by ownership. `app.models` remains as a temporary compatibility barrel during migration, but migrated slices import their own contract modules directly.

**Tech Stack:** Python 3.14, Pydantic, FastAPI OpenAPI generation, openapi-typescript via `scripts/generate-api-types.sh`, pytest, ruff, pyright.

---

## Dependency

Complete this plan first:

```text
docs/superpowers/plans/2026-05-06-architecture-boundary-cleanup.md
```

This follow-up assumes the module ownership charters and architecture helpers from that plan are available.

---

## File Structure

- Create `backend/app/contracts/__init__.py`
  - Marks shared contract helpers as a package.

- Create `backend/app/contracts/base.py`
  - Owns reusable Pydantic base classes: `DefaultsRequired`, `AutoTotalResponse`, and `StrictDefaultsRequired`.

- Modify `backend/app/models.py`
  - Re-export base classes under the old private names for compatibility.
  - Re-export moved slice contracts while the rest of the codebase migrates.
  - Stop defining the moved classes directly.

- Create `backend/app/domains/garmin_sync/contracts.py`
  - Owns ingest and sync API response contracts.

- Modify `backend/app/domains/garmin_sync/**`
  - Import ingest/sync contracts from `app.domains.garmin_sync.contracts`.

- Create `backend/app/domains/journal/contracts.py`
  - Owns journal/check-in/notes contracts that may be read by assistant and experiments.

- Modify `backend/app/domains/journal/**`
  - Import journal contracts from `app.domains.journal.contracts`.

- Modify `backend/app/domains/assistant/**` and `backend/app/domains/experiments/**`
  - Import `DailyCheckIn` from `app.domains.journal.contracts` where those modules read journal context.

- Modify architecture tests under `backend/tests/architecture/`
  - Guard migrated contract modules against falling back to `app.models`.
  - Guard `app.models` so moved classes are re-exported, not redefined.

- Modify `docs/ARCHITECTURE.md`
  - Add the contract ownership rule.

---

### Task 1: Extract Shared Contract Base Classes

**Files:**
- Create: `backend/app/contracts/__init__.py`
- Create: `backend/app/contracts/base.py`
- Modify: `backend/app/models.py`
- Create: `backend/tests/contracts/test_base_contracts.py`

- [ ] **Step 1: Write failing tests for shared contract behavior**

Create `backend/tests/contracts/test_base_contracts.py`:

```python
"""Tests for shared Pydantic contract base classes."""

from app.contracts.base import AutoTotalResponse, DefaultsRequired, StrictDefaultsRequired


class Item(DefaultsRequired):
    id: str
    label: str | None = None


class ItemsResponse(AutoTotalResponse, items_field="items"):
    items: list[Item] = []
    total: int = 0


class StrictItem(StrictDefaultsRequired):
    id: str


def test_defaults_required_marks_defaulted_fields_required_for_serialization_schema():
    schema = Item.model_json_schema(mode="serialization")

    assert set(schema["required"]) == {"id", "label"}


def test_auto_total_response_fills_total_from_items_when_missing():
    response = ItemsResponse(items=[Item(id="a"), Item(id="b")])

    assert response.total == 2


def test_auto_total_response_respects_explicit_total():
    response = ItemsResponse(items=[Item(id="a")], total=25)

    assert response.total == 25


def test_strict_defaults_required_rejects_unknown_keys():
    try:
        StrictItem.model_validate({"id": "a", "extra": "nope"})
    except Exception as exc:
        assert "extra" in str(exc)
    else:
        raise AssertionError("StrictItem accepted an unknown key")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/contracts/test_base_contracts.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.contracts'`.

- [ ] **Step 3: Create the shared contract package**

Create `backend/app/contracts/__init__.py`:

```python
"""Shared API contract helpers."""
```

Create `backend/app/contracts/base.py`:

```python
"""Shared Pydantic base classes for API and persistence contracts."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


class DefaultsRequired(BaseModel):
    """Make defaulted fields required in serialization JSON schema."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class AutoTotalResponse(DefaultsRequired):
    """Response base that auto-computes ``total`` from an items list field."""

    _items_field: ClassVar[str]

    def __init_subclass__(cls, items_field: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if items_field:
            cls._items_field = items_field

    @model_validator(mode="before")
    @classmethod
    def _auto_fill_total(cls, data: Any) -> Any:
        if isinstance(data, dict) and "total" not in data:
            items = data.get(cls._items_field)
            if isinstance(items, list):
                data["total"] = len(items)
        return data


class StrictDefaultsRequired(DefaultsRequired):
    """Defaults-required contract base that rejects unknown keys."""

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
    )
```

- [ ] **Step 4: Modify `backend/app/models.py` to use the shared bases**

Replace the current Pydantic base imports and base class definitions at the top of `backend/app/models.py`:

```python
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, model_validator
```

through the end of `_StrictDefaultsRequired` with:

```python
from typing import Literal

from app.contracts.base import (
    AutoTotalResponse as _AutoTotalResponse,
    DefaultsRequired as _DefaultsRequired,
    StrictDefaultsRequired as _StrictDefaultsRequired,
)
```

Keep the rest of `backend/app/models.py` unchanged in this task.

- [ ] **Step 5: Run the base contract tests**

Run:

```bash
cd backend && uv run pytest tests/contracts/test_base_contracts.py -v
```

Expected: PASS.

- [ ] **Step 6: Run a representative model schema test**

Run:

```bash
cd backend && uv run python -c "from app.models import IngestStatus; print(IngestStatus.model_json_schema(mode='serialization')['required'])"
```

Expected output includes:

```text
['needs_ingest', 'last_ingest_time', 'days_in_db', 'days_on_disk']
```

- [ ] **Step 7: Commit the shared contract base extraction**

```bash
git add backend/app/contracts/__init__.py backend/app/contracts/base.py backend/app/models.py backend/tests/contracts/test_base_contracts.py
git commit -m "refactor: extract shared contract base classes"
```

---

### Task 2: Add Contract Ownership Guardrails

**Files:**
- Modify: `backend/tests/architecture/test_architecture_garmin_sync_boundaries.py`
- Modify: `backend/tests/architecture/test_architecture_journal_boundaries.py`
- Create: `backend/tests/architecture/test_architecture_model_contracts.py`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Add failing guardrails for migrated contract ownership**

Create `backend/tests/architecture/test_architecture_model_contracts.py`:

```python
"""Architecture guard rails for draining app.models into owned contract modules."""

from tests._architecture import assert_no_text_in_files, read_repo_file


MOVED_GARMIN_SYNC_CONTRACTS = [
    "IngestResult",
    "IngestStatus",
    "SyncResult",
]

MOVED_JOURNAL_CONTRACTS = [
    "DailyCheckIn",
    "DailyCheckInsResponse",
    "Note",
    "NotesResponse",
]


def test_moved_contracts_are_not_defined_in_app_models():
    source = read_repo_file("backend/app/models.py")

    for name in MOVED_GARMIN_SYNC_CONTRACTS + MOVED_JOURNAL_CONTRACTS:
        assert f"class {name}(" not in source


def test_garmin_sync_imports_owned_contracts_directly():
    assert_no_text_in_files(
        [
            "backend/app/domains/garmin_sync/routes.py",
            "backend/app/domains/garmin_sync/use_cases.py",
            "backend/app/domains/garmin_sync/ports.py",
            "backend/app/domains/garmin_sync/adapters.py",
        ],
        ["from app.models import", "import app.models"],
    )


def test_journal_imports_owned_contracts_directly():
    assert_no_text_in_files(
        [
            "backend/app/domains/journal/api/checkins.py",
            "backend/app/domains/journal/api/notes.py",
            "backend/app/domains/journal/application/checkins.py",
            "backend/app/domains/journal/application/notes.py",
            "backend/app/domains/journal/application/ports.py",
            "backend/app/domains/journal/infra/sqlite_repository.py",
        ],
        ["from app.models import", "import app.models"],
    )
```

- [ ] **Step 2: Run the guardrail test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_model_contracts.py -v
```

Expected: FAIL because the listed contracts are still defined in `backend/app/models.py`.

- [ ] **Step 3: Document contract ownership in architecture docs**

In `docs/ARCHITECTURE.md`, add this subsection under "Migrated slice boundary convention":

```markdown
### Contract Ownership Convention

`backend/app/models.py` is a legacy compatibility barrel, not the home for new
contracts. New Pydantic contracts live with the module that owns the concept:

- shared Pydantic base classes live in `app/contracts/base.py`
- API request/response models live in the owning module's `contracts.py`
- persisted JSON record models live in the owning module's `contracts.py`
- application-only helper types live in `application/types.py`
- pure behavior and value helpers live under the owning module's `domain/`

Moving a contract must preserve OpenAPI schema names and fields unless the change
is intentionally an API change. After moving any route request/response contract,
run `bash scripts/generate-api-types.sh` and inspect
`frontend/src/lib/api-types.ts`.
```

- [ ] **Step 4: Run the contract guardrail test again**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_model_contracts.py -v
```

Expected: still FAIL. The docs are now ready, but contract files have not moved yet.

Do not commit this task yet. Commit after Tasks 3 and 4 make the guard pass.

---

### Task 3: Move Garmin Sync Contracts To `garmin_sync/contracts.py`

**Files:**
- Create: `backend/app/domains/garmin_sync/contracts.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/domains/garmin_sync/routes.py`
- Modify: `backend/app/domains/garmin_sync/use_cases.py`
- Modify: `backend/app/domains/garmin_sync/ports.py`
- Modify: `backend/app/domains/garmin_sync/adapters.py`
- Modify: `backend/tests/domains/garmin_sync/test_ingest_api.py`
- Modify: `backend/tests/domains/garmin_sync/test_ingest_application.py`

- [ ] **Step 1: Create Garmin sync contract module**

Create `backend/app/domains/garmin_sync/contracts.py`:

```python
"""Pydantic contracts owned by Garmin sync."""

from app.contracts.base import DefaultsRequired


class IngestResult(DefaultsRequired):
    days_ingested: int
    duration_ms: int


class IngestStatus(DefaultsRequired):
    needs_ingest: bool
    last_ingest_time: str | None = None
    days_in_db: int
    days_on_disk: int


class SyncResult(DefaultsRequired):
    downloaded: int
    skipped: int
    failed: int
    deleted_latest: str | None = None
    days_ingested: int
    duration_ms: int
```

- [ ] **Step 2: Re-export Garmin sync contracts from `app.models`**

In `backend/app/models.py`, add this import near the top after the base class import:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus, SyncResult
```

Then delete these class definitions from `backend/app/models.py`:

```python
class IngestResult(_DefaultsRequired):
    days_ingested: int
    duration_ms: int


class IngestStatus(_DefaultsRequired):
    needs_ingest: bool
    last_ingest_time: str | None = None
    days_in_db: int
    days_on_disk: int


class SyncResult(_DefaultsRequired):
    downloaded: int
    skipped: int
    failed: int
    deleted_latest: str | None = None
    days_ingested: int
    duration_ms: int
```

- [ ] **Step 3: Update Garmin sync implementation imports**

Replace `from app.models import IngestResult, IngestStatus, SyncResult` in `backend/app/domains/garmin_sync/routes.py` with:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus, SyncResult
```

Replace `from app.models import IngestResult, IngestStatus, SyncResult` in `backend/app/domains/garmin_sync/use_cases.py` with:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus, SyncResult
```

Replace `from app.models import IngestResult, IngestStatus` in `backend/app/domains/garmin_sync/ports.py` with:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
```

Replace `from app.models import IngestResult, IngestStatus` in `backend/app/domains/garmin_sync/adapters.py` with:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
```

- [ ] **Step 4: Update Garmin sync tests**

Replace `from app.models import IngestResult, IngestStatus, SyncResult` in `backend/tests/domains/garmin_sync/test_ingest_api.py` with:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus, SyncResult
```

Replace `from app.models import IngestResult, IngestStatus` in `backend/tests/domains/garmin_sync/test_ingest_application.py` with:

```python
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
```

Leave `backend/tests/bootstrap/test_main.py` importing from `app.models` in this task. That test covers app-level compatibility during the staged migration.

- [ ] **Step 5: Run Garmin sync tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_api.py tests/domains/garmin_sync/test_ingest_application.py -v
```

Expected: PASS.

- [ ] **Step 6: Run the contract ownership guard**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_model_contracts.py -v
```

Expected: FAIL only for the journal contracts, because Garmin sync contracts have moved.

Do not commit yet. Commit after Task 4 completes the first wave.

---

### Task 4: Move Journal Contracts To `journal/contracts.py`

**Files:**
- Create: `backend/app/domains/journal/contracts.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/domains/journal/api/checkins.py`
- Modify: `backend/app/domains/journal/api/notes.py`
- Modify: `backend/app/domains/journal/application/checkins.py`
- Modify: `backend/app/domains/journal/application/notes.py`
- Modify: `backend/app/domains/journal/application/ports.py`
- Modify: `backend/app/domains/journal/infra/sqlite_repository.py`
- Modify: `backend/app/domains/assistant/application/ports.py`
- Modify: `backend/app/domains/assistant/application/retrieval.py`
- Modify: `backend/app/domains/assistant/infra/sqlite_repository.py`
- Modify: `backend/app/domains/experiments/application/analysis.py`
- Modify: `backend/app/domains/experiments/application/analysis_math.py`
- Modify: `backend/app/domains/experiments/application/ports.py`
- Modify: `backend/app/domains/experiments/infra/sqlite_repository.py`
- Modify: `backend/tests/domains/journal/test_checkins_application.py`

- [ ] **Step 1: Create journal contract module**

Create `backend/app/domains/journal/contracts.py`:

```python
"""Pydantic contracts owned by journal."""

from app.contracts.base import AutoTotalResponse, DefaultsRequired


class DailyCheckIn(DefaultsRequired):
    id: str
    date: str
    energy: int | None = None
    mood: int | None = None
    motivation: int | None = None
    soreness: int | None = None
    stress_subjective: int | None = None
    sleep_quality_subjective: int | None = None
    workload_subjective: int | None = None
    illness_flag: bool = False
    travel_flag: bool = False
    alcohol_flag: bool = False
    notes: str | None = None


class Note(DefaultsRequired):
    id: str
    date: str
    category: str
    title: str
    content: str
    tags: list[str] = []


class DailyCheckInsResponse(AutoTotalResponse, items_field="checkins"):
    checkins: list[DailyCheckIn] = []
    total: int = 0


class NotesResponse(AutoTotalResponse, items_field="notes"):
    notes: list[Note] = []
    total: int = 0
```

- [ ] **Step 2: Re-export journal contracts from `app.models`**

In `backend/app/models.py`, add this import near the top after the Garmin sync contract import:

```python
from app.domains.journal.contracts import (
    DailyCheckIn,
    DailyCheckInsResponse,
    Note,
    NotesResponse,
)
```

Then delete these class definitions from `backend/app/models.py`:

```python
class DailyCheckIn(_DefaultsRequired):
    id: str
    date: str
    energy: int | None = None
    mood: int | None = None
    motivation: int | None = None
    soreness: int | None = None
    stress_subjective: int | None = None
    sleep_quality_subjective: int | None = None
    workload_subjective: int | None = None
    illness_flag: bool = False
    travel_flag: bool = False
    alcohol_flag: bool = False
    notes: str | None = None


class Note(_DefaultsRequired):
    id: str
    date: str
    category: str
    title: str
    content: str
    tags: list[str] = []
```

Then delete these response definitions from `backend/app/models.py`:

```python
class DailyCheckInsResponse(_AutoTotalResponse, items_field="checkins"):
    checkins: list[DailyCheckIn] = []
    total: int = 0


class NotesResponse(_AutoTotalResponse, items_field="notes"):
    notes: list[Note] = []
    total: int = 0
```

- [ ] **Step 3: Update journal module imports**

Replace journal imports from `app.models` with `app.domains.journal.contracts`:

```python
from app.domains.journal.contracts import DailyCheckIn, DailyCheckInsResponse
```

in:

```text
backend/app/domains/journal/api/checkins.py
backend/app/domains/journal/application/checkins.py
```

Replace journal note imports with:

```python
from app.domains.journal.contracts import Note, NotesResponse
```

in:

```text
backend/app/domains/journal/api/notes.py
backend/app/domains/journal/application/notes.py
```

Replace `from app.models import DailyCheckIn, Note` with:

```python
from app.domains.journal.contracts import DailyCheckIn, Note
```

in:

```text
backend/app/domains/journal/application/ports.py
backend/app/domains/journal/infra/sqlite_repository.py
```

- [ ] **Step 4: Update cross-slice journal readers**

In `backend/app/domains/assistant/application/ports.py`, remove `DailyCheckIn` from the `from app.models import (...)` list and add:

```python
from app.domains.journal.contracts import DailyCheckIn
```

In `backend/app/domains/assistant/application/retrieval.py`, remove `DailyCheckIn` from the `from app.models import (...)` list and add:

```python
from app.domains.journal.contracts import DailyCheckIn
```

In `backend/app/domains/assistant/infra/sqlite_repository.py`, remove `DailyCheckIn` from the `from app.models import (...)` list and add:

```python
from app.domains.journal.contracts import DailyCheckIn
```

In `backend/app/domains/experiments/application/analysis.py`, remove `DailyCheckIn` from the `from app.models import (...)` list and add:

```python
from app.domains.journal.contracts import DailyCheckIn
```

In `backend/app/domains/experiments/application/analysis_math.py`, replace:

```python
from app.models import DailyCheckIn, DailyMetric
```

with:

```python
from app.domains.journal.contracts import DailyCheckIn
from app.models import DailyMetric
```

In `backend/app/domains/experiments/application/ports.py`, remove `DailyCheckIn` from the `from app.models import (...)` list and add:

```python
from app.domains.journal.contracts import DailyCheckIn
```

In `backend/app/domains/experiments/infra/sqlite_repository.py`, remove `DailyCheckIn` from the `from app.models import (...)` list and add:

```python
from app.domains.journal.contracts import DailyCheckIn
```

- [ ] **Step 5: Update journal tests**

In `backend/tests/domains/journal/test_checkins_application.py`, replace:

```python
from app.models import DailyCheckIn, Note
```

with:

```python
from app.domains.journal.contracts import DailyCheckIn, Note
```

- [ ] **Step 6: Update cross-slice import allowlist**

In `backend/tests/architecture/test_architecture_cross_slice_imports.py`, add `app.domains.journal.contracts` to allowlist entries for files that now read check-ins:

```python
"backend/app/domains/assistant/application/ports.py": {
    "app.domains.journal.contracts",
},
"backend/app/domains/assistant/application/retrieval.py": {
    "app.domains.journal.contracts",
},
"backend/app/domains/assistant/infra/sqlite_repository.py": {
    "app.domains.experiments.application.analysis_cache",
    "app.domains.experiments.application.ports",
    "app.domains.journal.contracts",
},
"backend/app/domains/experiments/application/analysis.py": {
    "app.domains.journal.contracts",
},
"backend/app/domains/experiments/application/analysis_math.py": {
    "app.domains.journal.contracts",
},
"backend/app/domains/experiments/application/ports.py": {
    "app.domains.journal.contracts",
},
"backend/app/domains/experiments/infra/sqlite_repository.py": {
    "app.domains.journal.contracts",
},
```

If an entry already exists for one of these files, merge `app.domains.journal.contracts` into the existing set rather than duplicating the key.

- [ ] **Step 7: Run journal and dependent tests**

Run:

```bash
cd backend && uv run pytest tests/domains/journal/test_checkins_application.py tests/domains/assistant/test_assistant_retrieval.py tests/domains/experiments/test_experiment_analysis_math.py -v
```

Expected: PASS.

- [ ] **Step 8: Run architecture tests affected by this migration**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_model_contracts.py tests/architecture/test_architecture_cross_slice_imports.py tests/architecture/test_architecture_journal_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit the first contract ownership wave**

```bash
git add docs/ARCHITECTURE.md backend/app/domains/garmin_sync/contracts.py backend/app/domains/journal/contracts.py backend/app/models.py backend/app/domains/garmin_sync backend/app/domains/journal backend/app/domains/assistant backend/app/domains/experiments backend/tests/architecture backend/tests/domains/garmin_sync backend/tests/domains/journal
git commit -m "refactor: move first contracts to owning modules"
```

---

### Task 5: Verify OpenAPI And Frontend Type Stability

**Files:**
- Potentially modify: `frontend/src/lib/api-types.ts`

- [ ] **Step 1: Regenerate frontend API types**

Run:

```bash
bash scripts/generate-api-types.sh
```

Expected: script completes successfully.

- [ ] **Step 2: Inspect generated API type diff**

Run:

```bash
git diff -- frontend/src/lib/api-types.ts
```

Expected: no diff. If there is a diff, inspect it before continuing. A class move should not change API field names, nullability, required fields, or route paths.

- [ ] **Step 3: Commit generated API types only if the file changed for harmless ordering**

If `frontend/src/lib/api-types.ts` changed only because generated declarations were reordered, commit it:

```bash
git add frontend/src/lib/api-types.ts
git commit -m "chore: regenerate API types after contract moves"
```

If the diff changes field names, optionality, nullability, route paths, or schema names, stop and fix the backend contract move before committing.

---

### Task 6: Run Full Backend Validation

**Files:**
- No file edits.

- [ ] **Step 1: Run ruff**

Run:

```bash
cd backend && uv run ruff check
```

Expected: PASS with no reported errors.

- [ ] **Step 2: Run pyright**

Run:

```bash
cd backend && uv run pyright app/ tests/
```

Expected: PASS with 0 errors.

- [ ] **Step 3: Run backend tests**

Run:

```bash
cd backend && uv run pytest tests/ -v
```

Expected: PASS.

- [ ] **Step 4: Confirm `app.models` shrank**

Run:

```bash
wc -l backend/app/models.py
rg -n "class (IngestResult|IngestStatus|SyncResult|DailyCheckIn|DailyCheckInsResponse|Note|NotesResponse)\\(" backend/app/models.py
```

Expected: `wc -l` is lower than before the migration, and the `rg` command returns no matches.

---

### Task 7: Queue The Next Contract Slices

**Files:**
- Modify: `docs/backlog.md`

- [ ] **Step 1: Add concrete next contract extraction targets**

Append this section to `docs/backlog.md`:

```markdown
## Model Contract Extraction Queue

Rule: move contracts by owner, keep `app.models` as a temporary compatibility
barrel, and shrink compatibility imports after each slice proves OpenAPI stable.

Completed first wave:
- shared contract base classes moved to `app/contracts/base.py`
- Garmin sync contracts moved to `domains/garmin_sync/contracts.py`
- journal contracts moved to `domains/journal/contracts.py`

Next candidates:
1. `core/profile/contracts.py`
   - Move `DEFAULT_PROFILE_ID` and `UserProfile`.
   - Update profile API/application/ports/infra imports.

2. `domains/programs/contracts.py`
   - Move `ProgramStatus`, `Program`, `ProgramVersion`,
     `ProgramsResponse`, and `ProgramVersionsResponse`.
   - Update program API/application/ports/infra imports.

3. `domains/routines/contracts.py` and `domains/artifacts/contracts.py`
   - Split routine/card contracts from artifact/bundle contracts.
   - Refactor routine activation so it accepts `RoutineSpec` plus source metadata
     instead of an `AssistantArtifact` object.

4. `domains/garmin_analytics/contracts.py`
   - Move Garmin analytics response models after `app.stats` ownership is clearer.

5. `domains/experiments/contracts.py`
   - Move experiment contracts after journal and Garmin metric dependencies are
     direct owner imports.
```

- [ ] **Step 2: Commit the queue update**

```bash
git add docs/backlog.md
git commit -m "docs: queue model contract extraction"
```

---

## Completion Criteria

- `app/contracts/base.py` owns reusable Pydantic base classes.
- `garmin_sync` imports ingest/sync contracts from `app.domains.garmin_sync.contracts`.
- `journal` imports journal contracts from `app.domains.journal.contracts`.
- Assistant and experiments import `DailyCheckIn` from journal ownership rather than from `app.models`.
- `app.models` no longer defines `IngestResult`, `IngestStatus`, `SyncResult`, `DailyCheckIn`, `DailyCheckInsResponse`, `Note`, or `NotesResponse`.
- `app.models` still re-exports moved names for compatibility.
- `frontend/src/lib/api-types.ts` has no meaningful contract diff after regeneration.
- Backend validation passes:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```
