# Architecture Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the refactor from folder migration into enforceable module ownership, starting with architecture guardrails and a small Garmin sync pilot cleanup.

**Architecture:** Keep the existing package layout while adding explicit ownership contracts and tests that make accidental dumping-ground dependencies fail. Treat `garmin_sync` as a data acquisition capability module, not as a renamed service and not as `core`; use it as the first pilot for extracting workflow policy into focused, testable code.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, pytest, ruff, pyright, existing `backend/tests/architecture` guard pattern.

---

## File Structure

- Modify `docs/ARCHITECTURE.md`
  - Add a "Module Ownership Charters" section that defines `owns`, `does not own`, `may import`, `must not import`, and `public entrypoints` for current slices.
  - Reword `garmin_sync` as a data acquisition capability rather than a business domain.

- Modify `README.md`
  - Align the high-level architecture wording with capability/product/read-model slices.

- Modify `backend/tests/_architecture.py`
  - Add AST-based import helpers used by architecture tests.
  - Keep existing text-based helpers intact for current tests.

- Create `backend/tests/architecture/test_architecture_module_ownership.py`
  - Enforce documented slice charters in `docs/ARCHITECTURE.md`.

- Create `backend/tests/architecture/test_architecture_cross_slice_imports.py`
  - Enforce an explicit allowlist for cross-slice imports.

- Create `backend/tests/architecture/test_architecture_global_ownership.py`
  - Freeze direct imports from global shared buckets such as `app.stats` and `app.infra.cache` to an explicit allowlist.

- Create `backend/app/domains/garmin_sync/application/sync_plan.py`
  - Extract pure date-range and affected-date policy out of `ingest.py`.

- Modify `backend/app/domains/garmin_sync/application/ingest.py`
  - Use the pure sync plan helper while preserving public behavior.

- Modify `backend/tests/domains/garmin_sync/test_ingest_application.py`
  - Add focused tests for sync planning.
  - Keep existing orchestration tests.

- Modify `backend/tests/architecture/test_architecture_garmin_sync_boundaries.py`
  - Add the new `sync_plan.py` application file to strict boundary checks.

---

### Task 1: Add Module Ownership Charters To Architecture Docs

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `README.md`
- Test: `backend/tests/architecture/test_architecture_module_ownership.py`

- [ ] **Step 1: Write the failing architecture test for required charters**

Create `backend/tests/architecture/test_architecture_module_ownership.py`:

```python
"""Architecture guard rails for documented module ownership."""

from tests._architecture import read_repo_file


REQUIRED_MODULE_CHARTERS = [
    "assistant",
    "routines",
    "garmin_sync",
    "garmin_analytics",
    "experiments",
    "artifacts",
    "journal",
    "programs",
    "core/profile",
]

REQUIRED_CHARTER_FIELDS = [
    "Owns:",
    "Does not own:",
    "May import:",
    "Must not import:",
    "Public entrypoints:",
]


def test_architecture_documents_module_ownership_charters():
    source = read_repo_file("docs/ARCHITECTURE.md")

    for module in REQUIRED_MODULE_CHARTERS:
        heading = f"#### `{module}`"
        assert heading in source

        section_start = source.index(heading)
        next_heading = source.find("\n#### `", section_start + len(heading))
        section = source[section_start:] if next_heading == -1 else source[section_start:next_heading]

        for field in REQUIRED_CHARTER_FIELDS:
            assert field in section, f"{module} is missing {field}"


def test_garmin_sync_is_documented_as_capability_not_business_domain():
    source = read_repo_file("docs/ARCHITECTURE.md")

    section_start = source.index("#### `garmin_sync`")
    next_heading = source.find("\n#### `", section_start + 1)
    section = source[section_start:] if next_heading == -1 else source[section_start:next_heading]

    assert "data acquisition capability" in section
    assert "not a business domain" in section
    assert "FIT parsing semantics" in section
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_module_ownership.py -v
```

Expected: FAIL because `docs/ARCHITECTURE.md` does not yet contain the required `####` charter sections.

- [ ] **Step 3: Add charters to `docs/ARCHITECTURE.md`**

Insert this section after the existing "Active service areas" list and before "Migrated slice boundary convention":

```markdown
### Module Ownership Charters

These charters are the boundary source of truth. A module can be a product domain,
an operational capability, or an analytical read model; the package name alone is
not proof that the design is sound.

#### `assistant`

- Owns: assistant threads, messages, evidence bundle assembly, retrieval routing,
  assistant memory records, and runtime interaction.
- Does not own: Garmin parsing, Garmin ingest, routine scheduling writes,
  experiment exposure derivation, or artifact activation.
- May import: its own application/types/ports, `app.models` contracts, and
  explicitly allowlisted read dependencies needed to build evidence context.
- Must not import: Garmin sync, Garmin analytics application internals, routine
  activation internals, FastAPI from application modules, or SQLite helpers from
  application modules.
- Public entrypoints: `/api/assistant` routes and assistant application use cases
  called by those routes.

#### `routines`

- Owns: routine catalog reads, routine activation, assignment projection, Today
  card presentation, and Today log writes.
- Does not own: assistant artifact staging, experiment analysis, program import,
  Garmin ingest, or Garmin analytics.
- May import: its own pure schedule helpers, routine repository ports, and
  `app.models` routine/card contracts.
- Must not import: artifacts, experiments, assistant, Garmin sync, Garmin
  analytics, FastAPI from application modules, or SQLite helpers from application
  modules.
- Public entrypoints: `/api/routines`, `/api/today`, schedule-window use cases,
  and Today log use cases.

#### `garmin_sync`

- Owns: Garmin archive acquisition, ingest status, manual ingest orchestration,
  Garmin Connect wellness archive download orchestration, watcher suspension
  during sync, and affected-date ingest decisions.
- Does not own: FIT parsing semantics, analytics calculations, dashboard reads,
  experiment refresh policy, routine scheduling, assistant evidence, or frontend
  presentation.
- May import: its own ports, its own sync-planning helpers, `app.models`
  ingest/sync contracts, and infrastructure adapters that wrap database ingest,
  archive extraction, watcher control, filesystem writes, clock/sleep, and Garmin
  Connect login/download.
- Must not import: routines, experiments, assistant, artifacts, journal,
  programs, Garmin analytics application modules, FastAPI from application
  modules, or SQLite helpers from application modules.
- Public entrypoints: `/api/ingest`, `/api/ingest/status`, `/api/ingest/sync`,
  `trigger_ingest`, `get_ingest_status`, and `sync_garmin`.

`garmin_sync` is a data acquisition capability, not a business domain. It is core
to the product because the app depends on current local Garmin data, but `core/`
is reserved for shared app primitives rather than important product workflows.

#### `garmin_analytics`

- Owns: Garmin-derived read models, biometric API reads, dashboard overview,
  period summaries, metric drill-down insights, and recovery analysis responses.
- Does not own: archive acquisition, parser timestamp normalization, routine
  execution, experiment exposure derivation, assistant runtime behavior, or
  subjective journal writes.
- May import: its biometric repository port, Garmin analytics domain helpers,
  `app.models` Garmin analytics contracts, and currently allowlisted global
  analytics helpers while those helpers remain in `app.stats`.
- Must not import: Garmin sync, routines, experiments, assistant, artifacts,
  journal, programs, FastAPI from application modules, or SQLite helpers from
  application modules.
- Public entrypoints: dashboard, wellness, sleep, HRV, skin temperature, daily
  aggregate, heart-rate, stress, and body-battery API routes.

#### `experiments`

- Owns: experiment definitions, design preview/import, target metric registry,
  experiment-day exposures, cached N=1 analysis, and active-analysis refresh.
- Does not own: Today log storage, routine schedule projection internals beyond
  explicit routine ports/use cases, Garmin ingest, assistant runtime, or artifact
  staging.
- May import: experiment repository ports, allowlisted routine read/projection
  contracts needed for exposure derivation, `app.models` experiment contracts,
  and local analysis math helpers.
- Must not import: Garmin sync, Garmin analytics application internals except
  through persisted metric contracts, assistant runtime, artifact persistence
  internals, FastAPI from application modules, or SQLite helpers from application
  modules.
- Public entrypoints: `/api/experiments`, `/api/target-metrics`, experiment
  management use cases, exposure use cases, and analysis refresh/read use cases.

#### `artifacts`

- Owns: assistant-authored artifact staging, card template persistence before
  activation, bundle preview/import, bundle revision tracking, and capability
  request records.
- Does not own: live routine schedule semantics after activation, experiment
  protocol semantics, program lifecycle semantics, assistant chat runtime, or
  Garmin data.
- May import: artifact repository ports, `app.models` artifact/card/bundle
  contracts, and allowlisted routine activation contracts for publishing live
  cards/routines.
- Must not import: Garmin sync, Garmin analytics, journal, programs,
  experiments application internals, assistant runtime internals, FastAPI from
  application modules, or SQLite helpers from application modules.
- Public entrypoints: `/api/cards`, `/api/assistant/artifacts`,
  `/api/assistant/artifact-bundles`, bundle preview, and bundle import.

#### `journal`

- Owns: user-authored daily check-ins, freeform notes, and journal context that
  can later be read by assistant or experiment interpretation.
- Does not own: Garmin metrics, routine execution, experiment definitions,
  assistant runtime, or analytics computations.
- May import: journal repository ports and `app.models` journal contracts.
- Must not import: Garmin sync, Garmin analytics, routines, experiments,
  assistant, artifacts, programs, FastAPI from application modules, or SQLite
  helpers from application modules.
- Public entrypoints: `/api/checkins`, `/api/notes`, check-in use cases, and
  note use cases.

#### `programs`

- Owns: imported program specs, program lifecycle status, and program version
  history.
- Does not own: protocol activation, routine activation, experiment creation,
  artifact staging, Garmin data, or assistant runtime behavior.
- May import: program repository ports and `app.models` program contracts.
- Must not import: Garmin sync, Garmin analytics, assistant, artifacts, journal,
  routine activation internals, experiment management internals, FastAPI from
  application modules, or SQLite helpers from application modules.
- Public entrypoints: `/api/programs` and program import/list/read use cases.

#### `core/profile`

- Owns: app-level user profile configuration and profile persistence contracts.
- Does not own: Garmin data, routine runtime, experiments, assistant behavior,
  artifacts, journal content, programs, or analytics.
- May import: profile repository ports and `app.models` profile contracts.
- Must not import: any `app.domains.*` package, FastAPI from application modules,
  or unrelated SQLite helpers from application modules.
- Public entrypoints: `/api/profile` and profile read/write use cases.
```

- [ ] **Step 4: Update `README.md` high-level wording**

Replace this sentence:

```markdown
The backend is a FastAPI app under `backend/app/`. Its current direction is a
domain-oriented structure:
```

with:

```markdown
The backend is a FastAPI app under `backend/app/`. Its current direction is a
vertical module structure with explicit ownership contracts. Some modules are
product domains, some are operational capabilities, and some are analytical read
models; the boundary rules matter more than the package label:
```

Then replace the `domains/garmin_sync/` bullet with:

```markdown
- `domains/garmin_sync/` is a Garmin data acquisition capability. It owns
  `/api/ingest`, Garmin Connect wellness archive download orchestration, archive
  extraction, ingest status, and affected-date ingest decisions.
```

- [ ] **Step 5: Run the charter test**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_module_ownership.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the docs and charter test**

```bash
git add docs/ARCHITECTURE.md README.md backend/tests/architecture/test_architecture_module_ownership.py
git commit -m "docs: define backend module ownership charters"
```

---

### Task 2: Add Cross-Slice Import Guardrails

**Files:**
- Modify: `backend/tests/_architecture.py`
- Create: `backend/tests/architecture/test_architecture_cross_slice_imports.py`

- [ ] **Step 1: Write the failing cross-slice import test**

Create `backend/tests/architecture/test_architecture_cross_slice_imports.py`:

```python
"""Architecture guard rails for cross-slice imports."""

from tests._architecture import assert_cross_slice_imports_are_allowlisted


ALLOWLISTED_CROSS_SLICE_IMPORTS = {
    "backend/app/domains/artifacts/application/artifacts.py": {
        "app.domains.routines.application.activation",
        "app.domains.routines.application.ports",
    },
    "backend/app/domains/experiments/application/management.py": {
        "app.domains.routines.application.ports",
    },
    "backend/app/domains/experiments/application/preview.py": {
        "app.domains.routines.application.ports",
    },
    "backend/app/domains/experiments/application/exposure_sync.py": {
        "app.domains.routines.application.ports",
        "app.domains.routines.application.schedule_window",
    },
    "backend/app/domains/assistant/infra/sqlite_repository.py": {
        "app.domains.experiments.application.analysis_cache",
        "app.domains.experiments.application.ports",
    },
}


def test_cross_slice_imports_are_explicitly_allowlisted():
    assert_cross_slice_imports_are_allowlisted(ALLOWLISTED_CROSS_SLICE_IMPORTS)
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_cross_slice_imports.py -v
```

Expected: FAIL with an import error because `assert_cross_slice_imports_are_allowlisted` does not exist yet.

- [ ] **Step 3: Add AST import helpers to `backend/tests/_architecture.py`**

Append this code after `assert_no_repo_imports_of`:

```python
import ast


def _module_from_path(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT / "backend" / "app")
    return ".".join(("app", *relative.with_suffix("").parts))


def _slice_name(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) >= 4 and parts[:2] == ["app", "domains"]:
        return parts[2]
    if len(parts) >= 3 and parts[:2] == ["app", "core"]:
        return f"core/{parts[2]}"
    return None


def _source_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imports.add(node.module)

    return imports


def _app_slice_sources() -> list[Path]:
    roots = [
        REPO_ROOT / "backend" / "app" / "domains",
        REPO_ROOT / "backend" / "app" / "core",
    ]
    return sorted(
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def assert_cross_slice_imports_are_allowlisted(
    allowlist: Mapping[str, set[str]],
) -> None:
    offenders: dict[str, list[str]] = {}

    for path in _app_slice_sources():
        relative_path = str(path.relative_to(REPO_ROOT))
        source_module = _module_from_path(path)
        source_slice = _slice_name(source_module)
        if source_slice is None:
            continue

        allowed_for_file = allowlist.get(relative_path, set())
        bad_imports: list[str] = []

        for imported in _source_imports(path):
            imported_slice = _slice_name(imported)
            if imported_slice is None or imported_slice == source_slice:
                continue
            if imported not in allowed_for_file:
                bad_imports.append(imported)

        if bad_imports:
            offenders[relative_path] = sorted(bad_imports)

    assert offenders == {}
```

If `ast` is inserted below existing functions, move `import ast` to the import block at the top of the file so ruff keeps imports sorted:

```python
import ast
from collections.abc import Iterable, Mapping
from pathlib import Path
```

- [ ] **Step 4: Run the cross-slice import test**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_cross_slice_imports.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all architecture tests**

Run:

```bash
cd backend && uv run pytest tests/architecture/ -v
```

Expected: PASS.

- [ ] **Step 6: Commit the import guard**

```bash
git add backend/tests/_architecture.py backend/tests/architecture/test_architecture_cross_slice_imports.py
git commit -m "test: guard cross-slice imports"
```

---

### Task 3: Freeze Direct Imports From Global Shared Buckets

**Files:**
- Modify: `backend/tests/_architecture.py`
- Create: `backend/tests/architecture/test_architecture_global_ownership.py`

- [ ] **Step 1: Write the failing global ownership test**

Create `backend/tests/architecture/test_architecture_global_ownership.py`:

```python
"""Architecture guard rails for global shared bucket imports."""

from tests._architecture import assert_imports_from_module_match_allowlist


ALLOWLISTED_APP_STATS_IMPORTERS = {
    "backend/app/domains/garmin_analytics/application/biometrics.py",
    "backend/app/domains/garmin_analytics/application/body_battery_analysis.py",
    "backend/app/domains/garmin_analytics/application/heart_rate.py",
    "backend/app/domains/garmin_analytics/application/heart_rate_analysis.py",
    "backend/app/domains/garmin_analytics/application/hrv.py",
    "backend/app/domains/garmin_analytics/application/hrv_analysis.py",
    "backend/app/domains/garmin_analytics/application/overview.py",
    "backend/app/domains/garmin_analytics/application/period_summary.py",
    "backend/app/domains/garmin_analytics/application/sleep_analysis.py",
    "backend/app/domains/garmin_analytics/application/stress_analysis.py",
}

ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS = {
    "backend/app/domains/garmin_analytics/application/body_battery_analysis.py",
    "backend/app/domains/garmin_analytics/application/heart_rate_analysis.py",
    "backend/app/domains/garmin_analytics/application/hrv_analysis.py",
    "backend/app/domains/garmin_analytics/application/period_summary.py",
    "backend/app/domains/garmin_analytics/application/sleep_analysis.py",
    "backend/app/domains/garmin_analytics/application/stress_analysis.py",
}


def test_app_stats_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.stats",
        ALLOWLISTED_APP_STATS_IMPORTERS,
    )


def test_app_infra_cache_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.infra.cache",
        ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS,
        equivalent_imports={"app.infra"},
        required_import_name="cache",
    )
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_global_ownership.py -v
```

Expected: FAIL with an import error because `assert_imports_from_module_match_allowlist` does not exist yet.

- [ ] **Step 3: Add import allowlist helper to `backend/tests/_architecture.py`**

Append this code after `assert_cross_slice_imports_are_allowlisted`:

```python
def assert_imports_from_module_match_allowlist(
    module: str,
    allowlist: set[str],
    *,
    equivalent_imports: set[str] | None = None,
    required_import_name: str | None = None,
) -> None:
    equivalent_imports = equivalent_imports or set()
    import_roots = {module, *equivalent_imports}
    offenders: list[str] = []

    for root in [REPO_ROOT / "backend" / "app"]:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue

            relative_path = str(path.relative_to(REPO_ROOT))
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports_for_module = False

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports_for_module = any(
                        alias.name == module or alias.name.startswith(f"{module}.")
                        for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom):
                    if node.module == module:
                        imports_for_module = True
                    elif node.module in equivalent_imports and required_import_name is not None:
                        imports_for_module = any(
                            alias.name == required_import_name for alias in node.names
                        )

                if imports_for_module:
                    break

            if imports_for_module and relative_path not in allowlist:
                offenders.append(relative_path)

    assert offenders == []
```

- [ ] **Step 4: Run the global ownership test**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_global_ownership.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all architecture tests**

Run:

```bash
cd backend && uv run pytest tests/architecture/ -v
```

Expected: PASS.

- [ ] **Step 6: Commit the global ownership guard**

```bash
git add backend/tests/_architecture.py backend/tests/architecture/test_architecture_global_ownership.py
git commit -m "test: guard global analytics bucket imports"
```

---

### Task 4: Extract Garmin Sync Date Planning

**Files:**
- Create: `backend/app/domains/garmin_sync/application/sync_plan.py`
- Modify: `backend/app/domains/garmin_sync/application/ingest.py`
- Modify: `backend/tests/domains/garmin_sync/test_ingest_application.py`
- Modify: `backend/tests/architecture/test_architecture_garmin_sync_boundaries.py`

- [ ] **Step 1: Add failing sync-plan tests**

Append these tests to `backend/tests/domains/garmin_sync/test_ingest_application.py`:

```python
def test_sync_plan_redownloads_latest_archive_through_today():
    from app.domains.garmin_sync.application.sync_plan import plan_sync_dates

    plan = plan_sync_dates(
        latest=date(2026, 3, 14),
        today=date(2026, 3, 16),
    )

    assert plan.deleted_latest == date(2026, 3, 14)
    assert plan.dates == [
        date(2026, 3, 14),
        date(2026, 3, 15),
        date(2026, 3, 16),
    ]
    assert plan.initial_affected_dates == ["2026-03-14"]


def test_sync_plan_starts_with_yesterday_when_no_archive_exists():
    from app.domains.garmin_sync.application.sync_plan import plan_sync_dates

    plan = plan_sync_dates(
        latest=None,
        today=date(2026, 3, 16),
    )

    assert plan.deleted_latest is None
    assert plan.dates == [
        date(2026, 3, 15),
        date(2026, 3, 16),
    ]
    assert plan.initial_affected_dates == []
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_application.py::test_sync_plan_redownloads_latest_archive_through_today tests/domains/garmin_sync/test_ingest_application.py::test_sync_plan_starts_with_yesterday_when_no_archive_exists -v
```

Expected: FAIL with `ModuleNotFoundError` for `app.domains.garmin_sync.application.sync_plan`.

- [ ] **Step 3: Create `sync_plan.py`**

Create `backend/app/domains/garmin_sync/application/sync_plan.py`:

```python
"""Pure planning helpers for Garmin archive sync."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SyncDatePlan:
    deleted_latest: date | None
    dates: list[date]
    initial_affected_dates: list[str]


def plan_sync_dates(*, latest: date | None, today: date) -> SyncDatePlan:
    """Return the dates the sync workflow should inspect and refresh."""
    if latest is None:
        start_date = today - timedelta(days=1)
        deleted_latest = None
        initial_affected_dates: list[str] = []
    else:
        start_date = latest
        deleted_latest = latest
        initial_affected_dates = [latest.isoformat()]

    dates: list[date] = []
    current = start_date
    while current <= today:
        dates.append(current)
        current += timedelta(days=1)

    return SyncDatePlan(
        deleted_latest=deleted_latest,
        dates=dates,
        initial_affected_dates=initial_affected_dates,
    )
```

- [ ] **Step 4: Run the sync-plan tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_application.py::test_sync_plan_redownloads_latest_archive_through_today tests/domains/garmin_sync/test_ingest_application.py::test_sync_plan_starts_with_yesterday_when_no_archive_exists -v
```

Expected: PASS.

- [ ] **Step 5: Refactor `ingest.py` to use the pure plan**

In `backend/app/domains/garmin_sync/application/ingest.py`, remove `timedelta` from the imports:

```python
from datetime import date
```

Add the new import:

```python
from .sync_plan import plan_sync_dates
```

Replace this block inside `sync_garmin`:

```python
    latest = deps.files.latest_zip_date(deps.data_dir)
    today = deps.clock.today()
    deleted_latest: str | None = None

    deps.watcher.suspend()
    try:
        if latest is not None:
            deleted_latest = latest.isoformat()
            deps.files.remove_day(deps.data_dir, latest)
            start_date = latest
        else:
            start_date = today - timedelta(days=1)

        dates = []
        current = start_date
        while current <= today:
            dates.append(current)
            current += timedelta(days=1)
```

with:

```python
    latest = deps.files.latest_zip_date(deps.data_dir)
    plan = plan_sync_dates(latest=latest, today=deps.clock.today())
    deleted_latest = plan.deleted_latest.isoformat() if plan.deleted_latest else None

    deps.watcher.suspend()
    try:
        if plan.deleted_latest is not None:
            deps.files.remove_day(deps.data_dir, plan.deleted_latest)
```

Then replace:

```python
        affected_dates: list[str] = []
        if deleted_latest is not None:
            affected_dates.append(deleted_latest)

        for index, day in enumerate(dates):
```

with:

```python
        affected_dates = list(plan.initial_affected_dates)

        for index, day in enumerate(plan.dates):
```

Then replace:

```python
            if index < len(dates) - 1:
```

with:

```python
            if index < len(plan.dates) - 1:
```

- [ ] **Step 6: Update Garmin sync architecture boundary test**

In `backend/tests/architecture/test_architecture_garmin_sync_boundaries.py`, update `test_garmin_sync_application_modules_follow_strict_boundary`:

```python
def test_garmin_sync_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/garmin_sync/application/ingest.py",
        "backend/app/domains/garmin_sync/application/ports.py",
        "backend/app/domains/garmin_sync/application/sync_plan.py",
    ])
```

- [ ] **Step 7: Run Garmin sync application tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_application.py -v
```

Expected: PASS.

- [ ] **Step 8: Run Garmin sync architecture tests**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_garmin_sync_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit the Garmin sync pilot cleanup**

```bash
git add backend/app/domains/garmin_sync/application/ingest.py backend/app/domains/garmin_sync/application/sync_plan.py backend/tests/domains/garmin_sync/test_ingest_application.py backend/tests/architecture/test_architecture_garmin_sync_boundaries.py
git commit -m "refactor: extract Garmin sync planning"
```

---

### Task 5: Run Full Backend Validation

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

- [ ] **Step 4: Inspect diff for accidental rename-only churn**

Run:

```bash
git diff --stat HEAD~4..HEAD
git diff --name-status HEAD~4..HEAD
```

Expected: changes are limited to docs, architecture tests, `tests/_architecture.py`,
and the Garmin sync planning extraction. There should be no package-wide rename,
no route path changes, and no public API schema changes.

---

### Task 6: Decide The Next Cleanup Target From Evidence

**Files:**
- Modify: `docs/backlog.md`

- [ ] **Step 1: Add the next architecture cleanup queue**

Append this section to `docs/backlog.md`:

```markdown
## Architecture Cleanup Queue

Selection rule: the next cleanup must reduce coupling, shrink a shared bucket, or
make an illegal dependency executable in tests. Package renames do not qualify by
themselves.

1. Split `app.stats` by ownership.
   - First candidate: move Garmin-only period/window helpers behind
     `domains/garmin_analytics` contracts.
   - Success signal: one fewer file imports `app.stats`, and
     `test_architecture_global_ownership.py` allowlist shrinks.

2. Split `app.models` by ownership when a touched contract clearly belongs to one
   module.
   - First candidate: move ingest/sync response contracts near `garmin_sync`
     after confirming OpenAPI generation remains unchanged.
   - Success signal: no frontend API type diff except stable regeneration order.

3. Split `app.infra.database` by repository ownership.
   - First candidate: move Garmin biometric read helpers behind the existing
     `SqliteBiometricRepository` boundary.
   - Success signal: domain infra adapters call smaller database primitives or
     repositories instead of unrelated global save/load helpers.

4. Revisit assistant-to-experiments coupling.
   - Current allowlist: `assistant/infra/sqlite_repository.py` reads experiment
     analysis context.
   - Success signal: assistant depends on a read-model/evidence port instead of
     importing experiment analysis internals.

Follow-up implementation plan:
- `docs/superpowers/plans/2026-05-06-model-contract-ownership-cleanup.md`
  starts the `app.models` drain after these boundary guards are in place.
```

- [ ] **Step 2: Commit the backlog update**

```bash
git add docs/backlog.md
git commit -m "docs: queue evidence-based architecture cleanup"
```

---

## Completion Criteria

- `docs/ARCHITECTURE.md` defines explicit ownership charters for every current slice.
- Architecture tests fail if a new cross-slice import appears without being documented in an allowlist.
- Architecture tests fail if a new file imports `app.stats` or `app.infra.cache` without explicitly updating the global ownership allowlist.
- `garmin_sync` has a focused pure planning helper and tests for its date policy.
- No route paths, API response shapes, or frontend generated API types change.
- Backend validation passes:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```
