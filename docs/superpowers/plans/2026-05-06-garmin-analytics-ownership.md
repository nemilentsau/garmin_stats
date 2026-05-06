# Garmin Analytics Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Garmin analytics statistics and biometric read behavior out of broad shared buckets while preserving API behavior.

**Architecture:** Keep Garmin-specific aggregation, flattening, trend helpers, HR zones, and HRV status normalization inside `backend/app/domains/garmin_analytics/application/`. Use a tiny shared SQLite connection helper only for domain-neutral mechanics; Garmin repository code owns its biometric table reads and no longer imports `app.infra.database`. Shrink the Phase 0 architecture allowlists after each drain.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, ruff, pyright, numpy, generated OpenAPI TypeScript types.

---

## File Structure

- Create `backend/app/domains/garmin_analytics/application/numeric.py`
  - Owns simple nullable numeric helpers: `safe_avg`, `safe_median`, `safe_percentile`.
- Create `backend/app/domains/garmin_analytics/application/trends.py`
  - Owns Garmin analytics time-series helpers that operate on `DailyMetric`: `prior_7d_avg`, `trailing_ma7`, `group_by_iso_week`.
- Create `backend/app/domains/garmin_analytics/application/daily_aggregates.py`
  - Owns `HR_ZONE_THRESHOLDS`, `normalize_hrv_status`, `compute_hr_zones`, `aggregate_day`, `compute_daily_aggregates`.
- Create `backend/app/domains/garmin_analytics/application/period_aggregates.py`
  - Owns `compute_period_summary`.
- Create `backend/app/domains/garmin_analytics/application/biometric_responses.py`
  - Owns `flatten_wellness`, `flatten_sleep`, `flatten_hrv`, `flatten_skin_temp`.
- Create `backend/app/infra/sqlite.py`
  - Owns the domain-neutral SQLite connection helper and `DB_PATH`.
- Modify `backend/app/infra/database.py`
  - Import `connect`/`DB_PATH` from `app.infra.sqlite`.
  - Import `compute_daily_aggregates` from Garmin analytics.
  - Keep legacy biometric loader functions for test and transitional compatibility.
- Modify `backend/app/domains/garmin_analytics/infra/biometric_repository.py`
  - Load biometric records directly via repository-owned query helpers.
  - Import `connect` from `app.infra.sqlite` and `cache` from `app.infra.cache`.
  - Stop importing `app.infra.database`.
- Modify Garmin analytics application modules that import `app.stats`.
- Modify `backend/tests/domains/garmin_analytics/test_stats.py`
  - Retarget imports to the new Garmin analytics modules.
- Modify `backend/tests/architecture/test_architecture_global_ownership.py`
  - Set `ALLOWLISTED_APP_STATS_IMPORTERS` to an empty set.
  - Remove `backend/app/domains/garmin_analytics/infra/biometric_repository.py` from `ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS`.
  - Add new Garmin-owned modules to `ALLOWLISTED_APP_MODELS_IMPORTERS` because they now directly own model construction that was previously hidden inside `app.stats`.
  - Add `backend/app/domains/garmin_analytics/infra/biometric_repository.py` to `ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS` because the repository now owns cached biometric table reads.
- Modify test DB fixtures that monkeypatch `app.infra.database.DB_PATH`
  - Patch `app.infra.sqlite.DB_PATH` to the same temp path so legacy database helpers and new repository-owned reads share test isolation.

## Classification

Move these from `app.stats` into Garmin analytics:

- `safe_avg`, `safe_median`, `safe_percentile`: numeric helpers currently used only by Garmin analytics and Garmin stat tests.
- `prior_7d_avg`, `trailing_ma7`, `group_by_iso_week`: Garmin analytics trend helpers because they operate on `DailyMetric` or Garmin daily metric timelines.
- `HR_ZONE_THRESHOLDS`, `normalize_hrv_status`, `compute_hr_zones`: Garmin behavior.
- `flatten_wellness`, `flatten_sleep`, `flatten_hrv`, `flatten_skin_temp`: Garmin biometric response shaping.
- `aggregate_day`, `compute_period_summary`, `compute_daily_aggregates`: Garmin aggregate read-model behavior.

Do not create a shared numeric module in this phase. The roadmap allows shared extraction only when two domains use the exact same mechanical behavior; current use is Garmin analytics only.

## Task 1: Move Nullable Numeric And Trend Helpers

**Files:**
- Create: `backend/app/domains/garmin_analytics/application/numeric.py`
- Create: `backend/app/domains/garmin_analytics/application/trends.py`
- Modify: `backend/app/domains/garmin_analytics/application/body_battery_analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/heart_rate_analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/hrv_analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/sleep_analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/stress_analysis.py`
- Modify: `backend/tests/domains/garmin_analytics/test_stats.py`

- [ ] **Step 1: Create numeric helpers**

Create `backend/app/domains/garmin_analytics/application/numeric.py` with:

```python
"""Nullable numeric helpers for Garmin analytics read models."""

from collections.abc import Sequence

import numpy as np


def safe_avg(values: Sequence[int | float]) -> float | None:
    """Average with rounding, or None if empty."""
    return round(float(np.mean(values)), 1) if values else None


def safe_median(values: Sequence[int | float]) -> float | None:
    """Median with rounding, or None if empty."""
    return round(float(np.median(values)), 1) if values else None


def safe_percentile(values: Sequence[int | float], pct: float) -> float | None:
    """Percentile with rounding, or None if empty."""
    return round(float(np.percentile(values, pct)), 1) if values else None
```

- [ ] **Step 2: Create trend helpers**

Create `backend/app/domains/garmin_analytics/application/trends.py` with:

```python
"""Time-series helpers for Garmin analytics daily metric views."""

from collections.abc import Callable
from datetime import date as date_type

from app.models import DailyMetric


def prior_7d_avg(
    metrics: list[DailyMetric],
    selected_index: int,
    value_fn: Callable[[DailyMetric], float | None],
) -> float | None:
    """Average of `value_fn` over up to 7 metrics preceding `selected_index`."""
    previous = [
        v
        for v in (
            value_fn(m)
            for m in metrics[max(0, selected_index - 7) : selected_index]
        )
        if v is not None
    ]
    return round(sum(previous) / len(previous), 1) if previous else None


def trailing_ma7(values: list[float | None]) -> list[float | None]:
    """Compute 7-day trailing moving average, skipping None values."""
    result: list[float | None] = []
    for i in range(len(values)):
        window_start = max(0, i - 6)
        window = [v for v in values[window_start : i + 1] if v is not None]
        result.append(round(sum(window) / len(window), 1) if window else None)
    return result


def group_by_iso_week(
    metrics: list[DailyMetric],
    value_fn: Callable[[DailyMetric], float | None],
) -> dict[str, list[float]]:
    """Group daily metric values by ISO week, skipping None values."""
    weeks: dict[str, list[float]] = {}
    for metric in metrics:
        val = value_fn(metric)
        if val is None:
            continue
        try:
            metric_date = date_type.fromisoformat(metric.date)
        except ValueError:
            continue
        iso_year, iso_week, _ = metric_date.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weeks.setdefault(key, []).append(val)
    return weeks
```

- [ ] **Step 3: Retarget analysis imports**

Replace imports in these files:

```python
from app.stats import group_by_iso_week, safe_percentile, trailing_ma7
```

with:

```python
from .numeric import safe_percentile
from .trends import group_by_iso_week, trailing_ma7
```

Do this in:

- `backend/app/domains/garmin_analytics/application/body_battery_analysis.py`
- `backend/app/domains/garmin_analytics/application/heart_rate_analysis.py`
- `backend/app/domains/garmin_analytics/application/hrv_analysis.py`
- `backend/app/domains/garmin_analytics/application/sleep_analysis.py`
- `backend/app/domains/garmin_analytics/application/stress_analysis.py`

- [ ] **Step 4: Retarget stat helper tests**

In `backend/tests/domains/garmin_analytics/test_stats.py`, replace:

```python
from app.stats import (
    aggregate_day,
    compute_hr_zones,
    compute_period_summary,
    flatten_wellness,
    safe_avg,
    safe_median,
    safe_percentile,
)
```

with:

```python
from app.domains.garmin_analytics.application.numeric import (
    safe_avg,
    safe_median,
    safe_percentile,
)
from app.stats import (
    aggregate_day,
    compute_hr_zones,
    compute_period_summary,
    flatten_wellness,
)
```

- [ ] **Step 5: Verify focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py -v
```

Expected: all tests pass.

## Task 2: Move Daily Aggregate Behavior And HR Semantics

**Files:**
- Create: `backend/app/domains/garmin_analytics/application/daily_aggregates.py`
- Modify: `backend/app/domains/garmin_analytics/application/heart_rate.py`
- Modify: `backend/app/domains/garmin_analytics/application/hrv.py`
- Modify: `backend/app/domains/garmin_analytics/application/overview.py`
- Modify: `backend/app/infra/database.py`
- Modify: `backend/tests/domains/garmin_analytics/test_stats.py`

- [ ] **Step 1: Create daily aggregate module**

Create `backend/app/domains/garmin_analytics/application/daily_aggregates.py` by moving these definitions from `backend/app/stats.py`:

```python
HR_ZONE_THRESHOLDS
normalize_hrv_status
compute_hr_zones
aggregate_day
compute_daily_aggregates
```

The new module must import the Pydantic models it constructs from `app.models`, and must import numeric helpers from the new local module:

```python
from .numeric import safe_avg, safe_median, safe_percentile
```

- [ ] **Step 2: Retarget Garmin application imports**

In `backend/app/domains/garmin_analytics/application/heart_rate.py`, replace:

```python
from app.stats import HR_ZONE_THRESHOLDS, prior_7d_avg
```

with:

```python
from .daily_aggregates import HR_ZONE_THRESHOLDS
from .trends import prior_7d_avg
```

In `backend/app/domains/garmin_analytics/application/hrv.py`, replace:

```python
from app.stats import normalize_hrv_status, prior_7d_avg
```

with:

```python
from .daily_aggregates import normalize_hrv_status
from .trends import prior_7d_avg
```

In `backend/app/domains/garmin_analytics/application/overview.py`, replace:

```python
from app.stats import normalize_hrv_status, prior_7d_avg, trailing_ma7
```

with:

```python
from .daily_aggregates import normalize_hrv_status
from .trends import prior_7d_avg, trailing_ma7
```

- [ ] **Step 3: Retarget database ingest import**

In `backend/app/infra/database.py`, replace:

```python
from ..stats import compute_daily_aggregates
```

with:

```python
from ..domains.garmin_analytics.application.daily_aggregates import (
    compute_daily_aggregates,
)
```

- [ ] **Step 4: Retarget tests**

In `backend/tests/domains/garmin_analytics/test_stats.py`, import daily aggregate functions from the new module:

```python
from app.domains.garmin_analytics.application.daily_aggregates import (
    aggregate_day,
    compute_hr_zones,
)
```

Remove `aggregate_day` and `compute_hr_zones` from the temporary `app.stats` import.

- [ ] **Step 5: Verify focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py tests/infra/test_database.py -v
```

Expected: all tests pass.

## Task 3: Move Period Aggregation And Biometric Response Flattening

**Files:**
- Create: `backend/app/domains/garmin_analytics/application/period_aggregates.py`
- Create: `backend/app/domains/garmin_analytics/application/biometric_responses.py`
- Modify: `backend/app/domains/garmin_analytics/application/biometrics.py`
- Modify: `backend/app/domains/garmin_analytics/application/period_summary.py`
- Modify: `backend/tests/domains/garmin_analytics/test_stats.py`
- Modify: `backend/app/stats.py`

- [ ] **Step 1: Create period aggregate module**

Create `backend/app/domains/garmin_analytics/application/period_aggregates.py` by moving `compute_period_summary` from `backend/app/stats.py`.

The module must import these local helpers:

```python
from .daily_aggregates import compute_hr_zones
from .numeric import safe_avg, safe_percentile
```

- [ ] **Step 2: Create biometric response module**

Create `backend/app/domains/garmin_analytics/application/biometric_responses.py` by moving:

```python
flatten_wellness
flatten_sleep
flatten_hrv
flatten_skin_temp
```

from `backend/app/stats.py`.

- [ ] **Step 3: Retarget application imports**

In `backend/app/domains/garmin_analytics/application/biometrics.py`, replace:

```python
from app.stats import flatten_hrv, flatten_skin_temp, flatten_sleep, flatten_wellness
```

with:

```python
from .biometric_responses import (
    flatten_hrv,
    flatten_skin_temp,
    flatten_sleep,
    flatten_wellness,
)
```

In `backend/app/domains/garmin_analytics/application/period_summary.py`, replace:

```python
from app.stats import compute_period_summary
```

with:

```python
from .period_aggregates import compute_period_summary
```

- [ ] **Step 4: Retarget tests**

In `backend/tests/domains/garmin_analytics/test_stats.py`, import:

```python
from app.domains.garmin_analytics.application.biometric_responses import (
    flatten_wellness,
)
from app.domains.garmin_analytics.application.period_aggregates import (
    compute_period_summary,
)
```

Remove the remaining `app.stats` import.

- [ ] **Step 5: Remove drained `app.stats` module**

Delete `backend/app/stats.py` after `rg -n "app\\.stats|\\.\\.stats|from stats" backend/app backend/tests` returns only architecture-test literals or no real imports.

- [ ] **Step 6: Verify focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py tests/domains/garmin_analytics/test_dashboard_service.py -v
```

Expected: all tests pass.

## Task 4: Move Garmin Biometric Reads Behind The Repository Boundary

**Files:**
- Create: `backend/app/infra/sqlite.py`
- Modify: `backend/app/infra/database.py`
- Modify: `backend/app/domains/garmin_analytics/infra/biometric_repository.py`
- Modify: `backend/tests/architecture/test_architecture_global_ownership.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/domains/garmin_analytics/test_dashboard_service.py`
- Modify: `backend/tests/domains/garmin_analytics/test_heart_rate_service.py`
- Modify: `backend/tests/domains/garmin_analytics/test_hrv_service.py`

- [ ] **Step 1: Create SQLite connection helper**

Create `backend/app/infra/sqlite.py` with:

```python
"""SQLite connection primitives shared by persistence adapters."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import get_app_config

_APP_CONFIG = get_app_config()

DB_PATH = _APP_CONFIG.database_path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a sqlite3 connection with Row factory; close on exit."""
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
```

- [ ] **Step 2: Make database.py use the shared helper**

In `backend/app/infra/database.py`, remove the local `sqlite3`, `contextmanager`, and `get_app_config` imports if they become unused.

Replace:

```python
from ..core.config import get_app_config
```

and the local `_APP_CONFIG`, `DB_PATH`, and `_connect` definitions with:

```python
from .sqlite import DB_PATH, connect as _connect
```

Keep `DATA_DIR` sourced from config:

```python
from ..core.config import get_app_config

_APP_CONFIG = get_app_config()
DATA_DIR = _APP_CONFIG.data_dir
```

- [ ] **Step 3: Move biometric read queries into repository**

In `backend/app/domains/garmin_analytics/infra/biometric_repository.py`, replace the `app.infra.database` import with:

```python
from collections.abc import Callable

from pydantic import BaseModel

from app.infra import cache
from app.infra.sqlite import connect
from app.models import DailyMetric, DayHrv, DaySkinTemp, DaySleep, DayWellness
```

Add repository-owned helpers:

```python
def _load_daily_metrics() -> list[DailyMetric]:
    return cache.cached(cache.DAILY_METRICS, _fetch_daily_metrics)


def _fetch_daily_metrics() -> list[DailyMetric]:
    with connect() as con:
        rows = con.execute("SELECT data FROM daily_metrics ORDER BY date").fetchall()
    return [DailyMetric.model_validate_json(row["data"]) for row in rows]


def _load_day_table[M: BaseModel](
    table: str,
    model: type[M],
    cache_key: str,
    date: str | None = None,
) -> list[M]:
    if date is not None:
        all_cached = cache.get(cache_key)
        if all_cached is not None:
            return [item for item in all_cached if item.date == date]  # type: ignore[attr-defined]
        with connect() as con:
            rows = con.execute(
                f"SELECT data FROM {table} WHERE date = ?",  # noqa: S608
                (date,),
            ).fetchall()
        return [model.model_validate_json(row["data"]) for row in rows]

    hit = cache.get(cache_key)
    if hit is not None:
        return hit
    generation = cache.generation()
    with connect() as con:
        rows = con.execute(f"SELECT data FROM {table} ORDER BY date").fetchall()  # noqa: S608
    result = [model.model_validate_json(row["data"]) for row in rows]
    cache.put(cache_key, result, generation)
    return result
```

Then update `SqliteBiometricRepository` methods to call these helpers:

```python
def load_daily_metrics(self) -> list[DailyMetric]:
    return _load_daily_metrics()

def load_wellness(self, date: str | None = None) -> list[DayWellness]:
    return _load_day_table("wellness_data", DayWellness, cache.WELLNESS_ALL, date)

def load_sleep(self, date: str | None = None) -> list[DaySleep]:
    return _load_day_table("sleep_data", DaySleep, cache.SLEEP_ALL, date)

def load_hrv(self, date: str | None = None) -> list[DayHrv]:
    return _load_day_table("hrv_data", DayHrv, cache.HRV_ALL, date)

def load_skin_temp(self, date: str | None = None) -> list[DaySkinTemp]:
    return _load_day_table("skin_temp_data", DaySkinTemp, cache.SKIN_TEMP_ALL, date)
```

- [ ] **Step 4: Shrink architecture allowlists**

In `backend/tests/architecture/test_architecture_global_ownership.py`:

```python
ALLOWLISTED_APP_STATS_IMPORTERS = set()
```

Add the new Garmin analytics modules that import `app.models` to `ALLOWLISTED_APP_MODELS_IMPORTERS`:

```python
"backend/app/domains/garmin_analytics/application/biometric_responses.py",
"backend/app/domains/garmin_analytics/application/daily_aggregates.py",
"backend/app/domains/garmin_analytics/application/period_aggregates.py",
"backend/app/domains/garmin_analytics/application/trends.py",
```

Remove this line from `ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS`:

```python
"backend/app/domains/garmin_analytics/infra/biometric_repository.py",
```

Add this line to `ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS`:

```python
"backend/app/domains/garmin_analytics/infra/biometric_repository.py",
```

- [ ] **Step 5: Verify architecture tests**

Patch any fixture that monkeypatches `app.infra.database.DB_PATH` to also monkeypatch `app.infra.sqlite.DB_PATH` to the same temporary path. This keeps direct `db._connect()` setup writes and repository-owned reads isolated to the same test database.

Then run:

Run:

```bash
cd backend && uv run pytest tests/architecture -v
```

Expected: all tests pass.

## Task 5: Full Validation And Commit

**Files:**
- Modify: all files changed by Tasks 1-4.

- [ ] **Step 1: Run backend lint**

Run:

```bash
cd backend && uv run ruff check app/ tests/
```

Expected: `All checks passed!`

- [ ] **Step 2: Run backend type check**

Run:

```bash
cd backend && uv run pyright app/ tests/
```

Expected: `0 errors`.

- [ ] **Step 3: Run full backend tests**

Run:

```bash
cd backend && uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Confirm API types are not needed**

Run:

```bash
git diff --name-only
```

Expected: no route files and no Pydantic model schema files changed. If only application modules, repository modules, infra helper modules, architecture tests, and removed `app/stats.py` changed, skip API type generation.

- [ ] **Step 5: Commit Phase 1**

Run:

```bash
git add backend/app backend/tests docs/superpowers/plans/2026-05-06-garmin-analytics-ownership.md
git commit -m "refactor: tighten Garmin analytics ownership"
```

Expected: commit succeeds on the current branch.

## Self-Review

- Spec coverage:
  - Classify every `app.stats` function: covered in Classification.
  - Move Garmin behavior into Garmin analytics application modules: Tasks 1-3.
  - Avoid premature shared numeric module: Classification.
  - Move Garmin biometric reads behind repository boundary: Task 4.
  - Shrink `app.stats` and `app.infra.database` allowlists: Task 4.
  - Run backend lint, type check, and tests: Task 5.
- Placeholder scan:
  - No `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency:
  - New helpers keep current signatures.
  - Pydantic models remain imported from `app.models`, so OpenAPI schemas should not change.
