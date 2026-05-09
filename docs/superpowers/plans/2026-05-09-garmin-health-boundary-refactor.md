# Garmin Health Boundary Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move canonical Garmin health data contracts and raw-day-to-daily-metric composition out of `garmin_analytics` so persistence, parser, analytics, experiments, and assistant share a lower-level health data kernel.

**Architecture:** Add `backend/app/domains/garmin_health/` as the canonical Garmin health data slice. It owns parsed reading containers, persisted `DailyMetric` rows, nullable daily metric stat contracts, numeric summary helpers needed to build those rows, and the day-to-metric composer. `garmin_analytics` keeps dashboard, raw API response, period window, insight, and analysis DTOs and may consume `garmin_health`; repo-level infrastructure must not import analytics behavior or analytics response DTOs.

**Tech Stack:** FastAPI, Pydantic, SQLite persistence, Garmin FIT parser, pytest architecture tests, ruff, pyright.

---

## Target Boundaries

`garmin_health` owns:
- Parsed FIT reading models: `DayData`, `DayWellness`, `DaySleep`, `DayHrv`, `DaySkinTemp`, and individual reading rows.
- Persisted daily metric models: `DailyMetric`, `DailyMetricStats`, `DailyHeartRateStats`, `DailyHrvStats`, `DailySleepStats`, `DailySkinTempStats`, `DailyBodyBatteryStats`, and `HRZoneBucket`.
- Garmin-vocabulary metric calculators (e.g. `compute_daily_heart_rate`, `compute_hr_zones`, `normalize_hrv_status`, `classify_hrv_recovery`).
- Daily metric composition: `compute_daily_metric(day: DayData) -> DailyMetric` and `compute_daily_metrics(days: list[DayData]) -> list[DailyMetric]`.

`app/utils/` owns:
- Domain-agnostic numeric helpers (`safe_avg`, `safe_median`, `safe_min/max`, `safe_percentile`, `optional_float`, `summarize_scalar_values`, `ScalarSummary`, `HistogramBin`, `histogram_bins`, `percentile_rank`). These have primitive-only signatures and no Garmin vocabulary, so they belong above any domain. See `docs/ARCHITECTURE.md` → "Shared Utilities" for the promotion rule.

`garmin_analytics` owns:
- API/read response DTOs: raw endpoint responses, dashboard responses, insight responses, analysis responses, period summaries, and `DailyAggregatesResponse`.
- Read-domain computations over already persisted `DailyMetric` rows and reconstructed `DayData` period windows.

Forbidden final dependencies:
- `backend/app/infra/database.py` importing from `app.domains.garmin_analytics.domain` or `app.domains.garmin_analytics.utils`.
- `backend/app/infra/database.py` using `DailyAggregatesResponse`.
- Shared/canonical health models being defined in `app.domains.garmin_analytics.contracts`.
- `backend/app/domains/garmin_analytics/utils.py` existing as a shared behavior module.
- `backend/app/domains/garmin_analytics/domain/aggregates/daily.py`, `aggregates/daily_metrics/`, or `domain/primitives/numeric.py` existing after the refactor — these move out of analytics in the same PR.
- `backend/app/domains/garmin_health/domain/numeric.py` existing — generic numeric helpers live in `backend/app/utils/numeric.py`, not inside any domain.
- `app/utils/` containing any function whose name or signature uses Garmin vocabulary (HRV, body battery, etc.).

---

## Justification

The current problem is not only the import path. `compute_daily_aggregates` consumes `DayData`, returns analytics response shape, and is used by both read-domain analytics and write-path persistence. That means a persistence adapter currently depends on analytics-owned behavior and an analytics-owned API response DTO to produce canonical persisted rows. Moving that function to `garmin_analytics/utils.py` reduces the visual dependency on `domain/aggregates/daily.py`, but it does not fix ownership: `infra/database.py` still imports behavior from the analytics slice.

The data being composed is more fundamental than analytics. `DayData` is produced by the parser, shifted to local time at ingest, persisted by the database, reconstructed by analytics period windows, consumed by experiments, and exposed to assistant retrieval. `DailyMetric` is likewise the canonical persisted daily health row, not just a dashboard or analysis view. Those models need an owner below the read/analysis domain so every consumer can share one contract without depending on analytics.

`garmin_sync` is not the right owner because it describes acquisition and ingestion orchestration: archive extraction, file watching, startup/no-op detection, sync status, and workflow control. It should know how to get Garmin data into the app, but it should not own the semantic health model that downstream domains analyze after ingest. If `DailyMetric` and day-to-metric composition live in `garmin_sync`, then analytics, experiments, assistant, parser tests, and database persistence all become coupled to the sync lifecycle domain even when they only need canonical health data. That is the same boundary problem with a different feature slice.

The separate `garmin_health` slice is a deliberately narrow shared kernel. It owns stable Garmin health contracts and pure transformations from parsed readings to persisted daily metrics. It does not own sync workflows, API routes, database access, dashboard calculations, experiment analysis, or assistant retrieval. This keeps dependency direction simple: acquisition and persistence may use health contracts; analytics may read health contracts; health does not call back into acquisition, persistence, or analysis.

The intended dependency direction is:

```text
parser -> garmin_health, app.utils
garmin_sync -> parser / infra workflows / garmin_health contracts as needed
infra/database -> garmin_health
garmin_analytics -> garmin_health, app.utils
experiments -> garmin_health
assistant -> garmin_health
garmin_health -> app.contracts.base, app.utils
app.utils -> stdlib + numpy only
```

This also avoids recreating the old `app.models` dump. The new package is not a generic model bucket; it has one bounded responsibility: canonical Garmin health data and pure daily metric composition.

---

### Task 1: Add Failing Boundary Guardrails

**Files:**
- Create: `backend/tests/architecture/test_architecture_garmin_health_boundaries.py`
- Modify: `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`

- [ ] **Step 1: Add the Garmin health boundary test file**

Create `backend/tests/architecture/test_architecture_garmin_health_boundaries.py` with:

```python
"""Architecture guard rails for canonical Garmin health data ownership."""

from tests._architecture import REPO_ROOT, assert_no_text_in_files, read_repo_file


def test_garmin_health_owns_canonical_contracts_and_daily_metric_composer():
    base = REPO_ROOT / "backend/app/domains/garmin_health"

    for path in [
        base / "__init__.py",
        base / "contracts/__init__.py",
        base / "contracts/readings.py",
        base / "contracts/daily.py",
        base / "domain/__init__.py",
        base / "domain/daily.py",
        base / "domain/daily_metrics/__init__.py",
        base / "domain/daily_metrics/heart_rate.py",
        base / "domain/daily_metrics/stress.py",
        base / "domain/daily_metrics/body_battery.py",
        base / "domain/daily_metrics/spo2.py",
        base / "domain/daily_metrics/respiration.py",
        base / "domain/daily_metrics/hrv.py",
        base / "domain/daily_metrics/sleep.py",
        base / "domain/daily_metrics/skin_temp.py",
    ]:
        assert path.exists()

    assert not (base / "domain/numeric.py").exists()
    assert (REPO_ROOT / "backend/app/utils/numeric.py").exists()

    daily_source = read_repo_file("backend/app/domains/garmin_health/domain/daily.py")
    assert "def compute_daily_metric" in daily_source
    assert "def compute_daily_metrics" in daily_source
    assert "DailyAggregatesResponse" not in daily_source

    utils_numeric_source = read_repo_file("backend/app/utils/numeric.py")
    for forbidden in ("hrv", "body_battery", "garmin", "DayData", "DailyMetric"):
        assert forbidden.lower() not in utils_numeric_source.lower(), (
            f"app/utils/numeric.py must not contain Garmin vocabulary ({forbidden!r})"
        )


def test_infra_database_uses_garmin_health_not_garmin_analytics_behavior():
    source = read_repo_file("backend/app/infra/database.py")

    assert "app.domains.garmin_health.domain.daily import" in source
    assert "domains.garmin_analytics.domain" not in source
    assert "domains.garmin_analytics.utils" not in source
    assert "compute_daily_aggregates" not in source
    assert "DailyAggregatesResponse" not in source


def test_garmin_health_does_not_import_feature_domains():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/garmin_health").rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    assert_no_text_in_files(
        paths,
        [
            "app.domains.garmin_analytics",
            "app.domains.experiments",
            "app.domains.assistant",
            "app.infra.database",
        ],
    )
```

- [ ] **Step 2: Replace the temporary analytics-utils guard**

In `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`, replace `test_daily_aggregate_composer_shared_by_infra_lives_in_slice_utils` with:

```python
def test_garmin_analytics_does_not_own_canonical_daily_metric_composer():
    base = REPO_ROOT / "backend/app/domains/garmin_analytics"
    database_source = read_repo_file("backend/app/infra/database.py")

    assert not (base / "utils.py").exists()
    assert not (base / "contracts/daily.py").exists()
    assert not (base / "contracts/readings.py").exists()
    assert not (base / "domain/aggregates/daily.py").exists()
    assert not (base / "domain/aggregates/daily_metrics").exists()
    assert not (base / "domain/primitives/numeric.py").exists()
    assert "domains.garmin_analytics.utils" not in database_source
    assert "domains.garmin_analytics.domain.aggregates.daily" not in database_source
```

- [ ] **Step 3: Update the analytics contracts layout guard expectation**

In `test_garmin_analytics_contracts_are_split_by_concern_with_stable_imports`, remove `readings.py` and `daily.py` from the expected analytics contracts files, and replace the final `DailyMetric` assertion with an analytics-owned response assertion:

```python
    for filename in [
        "__init__.py",
        "raw.py",
        "period.py",
        "insights.py",
        "analysis.py",
        "dashboard.py",
    ]:
        assert (contracts_root / filename).exists()

    assert contracts.DailyAggregatesResponse.__name__ == "DailyAggregatesResponse"
    assert contracts.DashboardOverviewResponse.__name__ == "DashboardOverviewResponse"
```

- [ ] **Step 4: Run the architecture tests and confirm they fail for the expected reasons**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_garmin_health_boundaries.py tests/architecture/test_architecture_garmin_analytics_boundaries.py -v
```

Expected: failures mention missing `garmin_health` files and the current `garmin_analytics/utils.py` or analytics daily/readings contracts.

---

### Task 2: Create `garmin_health` Contracts And Daily Composer

**Files:**
- Create: `backend/app/domains/garmin_health/__init__.py`
- Create: `backend/app/domains/garmin_health/contracts/__init__.py`
- Create: `backend/app/domains/garmin_health/contracts/readings.py`
- Create: `backend/app/domains/garmin_health/contracts/daily.py`
- Create: `backend/app/domains/garmin_health/domain/__init__.py`
- Create: `backend/app/utils/numeric.py` (moved from `backend/app/domains/garmin_analytics/domain/primitives/numeric.py`)
- Create: `backend/app/domains/garmin_health/domain/daily.py`
- Create: `backend/app/domains/garmin_health/domain/daily_metrics/*.py`
- Create: `backend/tests/domains/garmin_health/__init__.py`
- Test: `backend/tests/domains/garmin_health/test_daily_metrics.py`

- [ ] **Step 1: Create the package docstrings**

Use these docstrings:

```python
# backend/app/domains/garmin_health/__init__.py
"""Canonical Garmin health data contracts and metric composition."""
```

```python
# backend/app/domains/garmin_health/domain/__init__.py
"""Pure Garmin health computations used by ingest and read domains."""
```

- [ ] **Step 2: Move canonical contracts**

Copy the class definitions from:
- `backend/app/domains/garmin_analytics/contracts/readings.py`
- `backend/app/domains/garmin_analytics/contracts/daily.py`

into:
- `backend/app/domains/garmin_health/contracts/readings.py`
- `backend/app/domains/garmin_health/contracts/daily.py`

Keep the same class names and fields. Update only the module docstrings:

```python
"""Canonical parsed Garmin reading rows and day-level containers."""
```

```python
"""Canonical persisted Garmin daily metric contracts."""
```

- [ ] **Step 3: Add `garmin_health.contracts` public exports**

Create `backend/app/domains/garmin_health/contracts/__init__.py` with exports for every class from `readings.py` and `daily.py`:

```python
"""Public canonical Garmin health contracts."""

from .daily import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    HRZoneBucket,
)
from .readings import (
    ActivityReading,
    BodyBatteryReading,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvSummary,
    HrvValue,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SleepLevel,
    SpO2Reading,
    StepsReading,
    StressReading,
)

__all__ = [
    "ActivityReading",
    "BodyBatteryReading",
    "DailyBodyBatteryStats",
    "DailyHeartRateStats",
    "DailyHrvStats",
    "DailyMetric",
    "DailyMetricStats",
    "DailySkinTempStats",
    "DailySleepStats",
    "DayData",
    "DayHrv",
    "DaySkinTemp",
    "DaySleep",
    "DayWellness",
    "HeartRateReading",
    "HRZoneBucket",
    "HrvSummary",
    "HrvValue",
    "RespirationReading",
    "RestingHRReading",
    "SkinTempOvernight",
    "SleepAssessment",
    "SleepLevel",
    "SpO2Reading",
    "StepsReading",
    "StressReading",
]
```

- [ ] **Step 4: Move numeric helpers wholesale to `app/utils/`**

Move (do not duplicate) `backend/app/domains/garmin_analytics/domain/primitives/numeric.py` to `backend/app/utils/numeric.py`. The module is domain-agnostic — `ScalarSummary`, `optional_float`, `safe_avg`, `safe_median`, `safe_percentile`, `safe_min`, `safe_max`, `summarize_scalar_values`, `HistogramBin`, `histogram_bins`, `percentile_rank` all have primitive-only signatures and no Garmin vocabulary. They satisfy the shared-utility promotion rule (see `docs/ARCHITECTURE.md` → "Shared Utilities"), so they belong above any domain.

Update the module docstring to drop the Garmin reference:

```python
"""Null-tolerant scalar summary, histogram, and percentile helpers."""
```

Delete `backend/app/domains/garmin_analytics/domain/primitives/numeric.py`. Analytics callers (`domain/dashboard.py`, `domain/insights/hrv.py`, `domain/insights/heart_rate.py`, `domain/analysis/body_battery.py`, `domain/analysis/stress.py`, `domain/analysis/sleep.py`, `domain/analysis/hrv.py`, `domain/analysis/heart_rate.py`) are updated in Task 4 Step 3 to import from `app.utils.numeric` instead.

Do **not** create `backend/app/domains/garmin_health/domain/numeric.py`. Generic numeric helpers must not live inside any domain.

- [ ] **Step 5: Move daily metric calculators**

Create `backend/app/domains/garmin_health/domain/daily_metrics/` by copying the current files from `backend/app/domains/garmin_analytics/domain/aggregates/daily_metrics/`.

In the copied files, replace imports:

```python
from app.domains.garmin_analytics.contracts import ...
from app.domains.garmin_analytics.domain.primitives.numeric import ...
```

with:

```python
from app.domains.garmin_health.contracts import ...
from app.utils.numeric import ...
```

- [ ] **Step 6: Add the canonical day-to-metric composer**

Create `backend/app/domains/garmin_health/domain/daily.py`:

```python
"""Compose canonical persisted daily metric rows from parsed Garmin days."""

from app.domains.garmin_health.contracts import DailyMetric, DayData
from app.domains.garmin_health.domain.daily_metrics import (
    compute_daily_body_battery,
    compute_daily_heart_rate,
    compute_daily_hrv,
    compute_daily_respiration,
    compute_daily_skin_temp,
    compute_daily_sleep,
    compute_daily_spo2,
    compute_daily_stress,
)


def compute_daily_metric(day: DayData) -> DailyMetric:
    """Compute the persisted daily metric row for one parsed Garmin day."""
    return DailyMetric(
        date=day.date,
        utc_offset_hours=day.utc_offset_hours,
        heart_rate=compute_daily_heart_rate(day.wellness),
        stress=compute_daily_stress(day.wellness),
        body_battery=compute_daily_body_battery(day.wellness),
        spo2=compute_daily_spo2(day.wellness),
        respiration=compute_daily_respiration(day.wellness),
        hrv=compute_daily_hrv(day.hrv),
        sleep=compute_daily_sleep(day.sleep),
        skin_temp=compute_daily_skin_temp(day.skin_temp),
    )


def compute_daily_metrics(days: list[DayData]) -> list[DailyMetric]:
    """Compute persisted daily metric rows for parsed Garmin days."""
    return [compute_daily_metric(day) for day in days]
```

- [ ] **Step 7: Add health-domain daily metric tests**

Create `backend/tests/domains/garmin_health/test_daily_metrics.py` by moving the `aggregate_day` tests from `backend/tests/domains/garmin_analytics/test_stats.py` and updating them to import:

```python
from app.domains.garmin_health.contracts import (
    BodyBatteryReading,
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvSummary,
    HrvValue,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SleepLevel,
    SpO2Reading,
    StressReading,
)
from app.domains.garmin_health.domain.daily import compute_daily_metric
from app.domains.garmin_health.domain.daily_metrics import (
    classify_hrv_recovery,
    compute_hr_zones,
    is_balanced_hrv_status,
    is_unfavorable_hrv_status,
    normalize_hrv_status,
)
```

Rename assertions from `aggregate_day(day)` to `compute_daily_metric(day)`.

- [ ] **Step 8: Run the new health-domain tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_health/test_daily_metrics.py -v
```

Expected: the new tests pass.

---

### Task 3: Switch Parser And Persistence To `garmin_health`

**Files:**
- Modify: `backend/app/parser.py`
- Modify: `backend/app/infra/database.py`
- Modify: `backend/tests/infra/test_parser.py`
- Modify: `backend/tests/infra/test_database.py`
- Modify: `backend/tests/architecture/test_architecture_cross_slice_imports.py`

- [ ] **Step 1: Update parser contract imports**

In `backend/app/parser.py`, replace:

```python
from app.domains.garmin_analytics.contracts import (
```

with:

```python
from app.domains.garmin_health.contracts import (
```

- [ ] **Step 2: Update database daily metric composition**

In `backend/app/infra/database.py`, replace the temporary analytics utility import:

```python
from ..domains.garmin_analytics.utils import (
    compute_daily_aggregates,
)
```

with:

```python
from ..domains.garmin_health.domain.daily import (
    compute_daily_metric,
    compute_daily_metrics,
)
```

Then replace:

```python
agg = compute_daily_aggregates(all_days)
...
for metric in agg.daily:
```

with:

```python
daily_metrics = compute_daily_metrics(all_days)
...
for metric in daily_metrics:
```

And replace:

```python
metric = compute_daily_aggregates([day]).daily[0]
```

with:

```python
metric = compute_daily_metric(day)
```

- [ ] **Step 3: Update parser and database tests**

In `backend/tests/infra/test_parser.py` and `backend/tests/infra/test_database.py`, replace imports from:

```python
from app.domains.garmin_analytics.contracts import (
```

with:

```python
from app.domains.garmin_health.contracts import (
```

- [ ] **Step 4: Run focused infra verification**

Run:

```bash
cd backend && uv run pytest tests/infra/test_parser.py tests/infra/test_database.py tests/architecture/test_architecture_garmin_health_boundaries.py -v
```

Expected: parser and database tests pass; architecture may still fail on analytics-owned old files until later tasks remove them.

---

### Task 4: Switch Analytics, Experiments, And Assistant To Canonical Health Contracts

**Files:**
- Modify: `backend/app/domains/garmin_analytics/**/*.py`
- Modify: `backend/app/domains/experiments/**/*.py`
- Modify: `backend/app/domains/assistant/**/*.py`
- Modify: `backend/tests/domains/garmin_analytics/**/*.py`
- Modify: `backend/tests/domains/experiments/**/*.py`
- Modify: `backend/tests/domains/assistant/**/*.py`
- Modify: `backend/tests/architecture/test_architecture_cross_slice_imports.py`

- [ ] **Step 1: Update analytics imports of canonical health contracts**

In analytics modules, replace imports of canonical data models from:

```python
from app.domains.garmin_analytics.contracts import DailyMetric
from app.domains.garmin_analytics.contracts import DayData
```

with:

```python
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.garmin_health.contracts import DayData
```

Apply the same replacement for reading and daily stat models such as `DayWellness`, `DaySleep`, `DayHrv`, `DaySkinTemp`, `DailyMetricStats`, `DailyHeartRateStats`, and `HRZoneBucket`.

- [ ] **Step 2: Update analytics daily metric helper imports**

Replace imports from:

```python
from app.domains.garmin_analytics.domain.aggregates.daily import (
    HR_ZONE_THRESHOLDS,
    classify_hrv_recovery,
    compute_hr_zones,
    is_balanced_hrv_status,
    is_unfavorable_hrv_status,
    normalize_hrv_status,
)
```

with imports from the canonical health metric modules:

```python
from app.domains.garmin_health.domain.daily_metrics import (
    HR_ZONE_THRESHOLDS,
    classify_hrv_recovery,
    compute_hr_zones,
    is_balanced_hrv_status,
    is_unfavorable_hrv_status,
    normalize_hrv_status,
)
```

- [ ] **Step 3: Update analytics numeric imports to point at `app/utils/`**

Replace every analytics import of:

```python
from app.domains.garmin_analytics.domain.primitives.numeric import (
```

with:

```python
from app.utils.numeric import (
```

Files that need updating: `domain/dashboard.py`, `domain/insights/hrv.py`, `domain/insights/heart_rate.py`, `domain/analysis/body_battery.py`, `domain/analysis/stress.py`, `domain/analysis/sleep.py`, `domain/analysis/hrv.py`, `domain/analysis/heart_rate.py`.

The final rule is that `garmin_health` and `garmin_analytics` both consume numeric helpers from `app.utils.numeric`. Neither domain re-exports them. `garmin_analytics/domain/primitives/` keeps `timestamps.py`, `trends.py`, and `windows.py` (analytics-only — these have period semantics in their signatures, so they stay).

- [ ] **Step 4: Update `DailyAggregatesResponse` to wrap health metrics**

In `backend/app/domains/garmin_analytics/contracts/period.py`, replace:

```python
from .daily import DailyMetric, HRZoneBucket
```

with:

```python
from app.domains.garmin_health.contracts import DailyMetric, HRZoneBucket
```

Keep `DailyAggregatesResponse` in analytics because it is an API response DTO:

```python
class DailyAggregatesResponse(DefaultsRequired):
    days: list[str]
    daily: list[DailyMetric]
    period_windows: dict[str, PeriodSummary] = {}
```

- [ ] **Step 5: Update analytics daily aggregates application**

In `backend/app/domains/garmin_analytics/application/daily_aggregates.py`, import `DayData` from `garmin_health.contracts` and import `compute_daily_metrics` from `garmin_health.domain.daily`.

The endpoint application should wrap canonical metrics into the analytics response. Preserve the current `period_windows` behavior — today the value comes from `compute_windows(...)`; do **not** introduce a new placeholder. If the current code path does not populate `period_windows`, omit it (the default `{}` from the model applies). Concretely:

```python
daily_metrics = compute_daily_metrics(days)
return DailyAggregatesResponse(
    days=[d.date for d in days],
    daily=daily_metrics,
    period_windows=compute_windows(...),  # keep whatever the current call passes
)
```

Verify by diffing the response shape against the pre-refactor endpoint output for at least one date range before declaring this step done.

- [ ] **Step 6: Update experiments and assistant imports**

In experiments and assistant modules, replace:

```python
from app.domains.garmin_analytics.contracts import DailyMetric
```

with:

```python
from app.domains.garmin_health.contracts import DailyMetric
```

Keep imports of `app.domains.garmin_analytics.adapters` only where a read adapter is intentionally used to load persisted metrics.

- [ ] **Step 7: Update cross-slice import allowlists**

In `backend/tests/architecture/test_architecture_cross_slice_imports.py`, replace allowlist entries for canonical health contracts:

```python
"app.domains.garmin_analytics.contracts",
```

with:

```python
"app.domains.garmin_health.contracts",
```

for experiments and assistant files that only need `DailyMetric`.

Add `app.domains.garmin_health.contracts`, `app.domains.garmin_health.domain.daily`, `app.domains.garmin_health.domain.daily_metrics`, or `app.domains.garmin_health.domain.numeric` to analytics files that legitimately consume health models or helpers.

- [ ] **Step 8: Run focused domain tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics tests/domains/experiments tests/domains/assistant tests/architecture/test_architecture_cross_slice_imports.py -v
```

Expected: domain tests pass, except architecture tests may still fail until old analytics-owned canonical files are removed in Task 5.

---

### Task 5: Remove Analytics-Owned Canonical Health Modules

**Files:**
- Delete: `backend/app/domains/garmin_analytics/utils.py`
- Delete: `backend/app/domains/garmin_analytics/contracts/daily.py`
- Delete: `backend/app/domains/garmin_analytics/contracts/readings.py`
- Delete: `backend/app/domains/garmin_analytics/domain/aggregates/daily.py`
- Delete: `backend/app/domains/garmin_analytics/domain/aggregates/daily_metrics/` (entire package; canonical copy now lives in `garmin_health`)
- Delete: `backend/app/domains/garmin_analytics/domain/primitives/numeric.py` (moved to `garmin_health/domain/numeric.py` in Task 2)
- Modify: `backend/app/domains/garmin_analytics/contracts/__init__.py`
- Modify: `backend/app/domains/garmin_analytics/contracts/raw.py`
- Modify: `backend/app/domains/garmin_analytics/contracts/insights.py`
- Modify: `backend/app/domains/garmin_analytics/domain/aggregates/__init__.py` (drops `daily` and `daily_metrics` re-exports; keeps period/biometric_responses re-exports if any)
- Modify: `backend/app/domains/garmin_analytics/domain/primitives/__init__.py` (drops `numeric` re-export)
- Modify: `backend/tests/domains/garmin_analytics/test_stats.py`

- [ ] **Step 1: Delete the temporary analytics utility**

Remove:

```text
backend/app/domains/garmin_analytics/utils.py
```

No replacement should exist inside analytics. Database and analytics daily aggregate use cases should already call `garmin_health.domain.daily`.

- [ ] **Step 2: Delete analytics canonical contract modules**

Remove:

```text
backend/app/domains/garmin_analytics/contracts/daily.py
backend/app/domains/garmin_analytics/contracts/readings.py
```

Analytics response DTO modules that need canonical data types must import them from `app.domains.garmin_health.contracts`.

- [ ] **Step 3: Update analytics contracts exports**

In `backend/app/domains/garmin_analytics/contracts/__init__.py`, remove imports and `__all__` entries for:

```python
ActivityReading
BodyBatteryReading
DailyBodyBatteryStats
DailyHeartRateStats
DailyHrvStats
DailyMetric
DailyMetricStats
DailySkinTempStats
DailySleepStats
DayData
DayHrv
DaySkinTemp
DaySleep
DayWellness
HeartRateReading
HRZoneBucket
HrvSummary
HrvValue
RespirationReading
RestingHRReading
SkinTempOvernight
SleepAssessment
SleepLevel
SpO2Reading
StepsReading
StressReading
```

Keep analytics-owned response DTOs exported, including `DailyAggregatesResponse`, raw responses, dashboard responses, analysis responses, and insight responses.

- [ ] **Step 4: Delete analytics daily aggregate helper modules**

Remove:

```text
backend/app/domains/garmin_analytics/domain/aggregates/daily.py
backend/app/domains/garmin_analytics/domain/aggregates/daily_metrics/
backend/app/domains/garmin_analytics/domain/primitives/numeric.py
```

The canonical copies now live in `garmin_health`. Leaving the analytics copies in place produces silent duplication (two implementations of `compute_daily_heart_rate`, `safe_avg`, etc., diverging over time).

Update `backend/app/domains/garmin_analytics/domain/aggregates/__init__.py` to drop the `daily` and `daily_metrics` re-exports. The `aggregates/` package keeps `period.py`, `period_metrics/`, and `biometric_responses.py` (analytics-only period concerns).

Update `backend/app/domains/garmin_analytics/domain/primitives/__init__.py` to drop the `numeric` re-export. The package keeps `timestamps.py`, `trends.py`, and `windows.py`.

Update any remaining imports to one of:

```python
from app.domains.garmin_health.domain.daily import compute_daily_metric, compute_daily_metrics
from app.domains.garmin_health.domain.daily_metrics import normalize_hrv_status
from app.utils.numeric import optional_float, ScalarSummary
```

- [ ] **Step 5: Split analytics stats tests**

In `backend/tests/domains/garmin_analytics/test_stats.py`, remove tests for `aggregate_day`, `compute_hr_zones`, HRV status normalization, and daily metric calculator details that now live in `backend/tests/domains/garmin_health/test_daily_metrics.py`.

Keep analytics tests focused on period windows, API response wrapping, dashboard, insights, and analysis behavior.

- [ ] **Step 6: Run architecture and moved test verification**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_garmin_health_boundaries.py tests/architecture/test_architecture_garmin_analytics_boundaries.py tests/domains/garmin_health/test_daily_metrics.py tests/domains/garmin_analytics/test_stats.py -v
```

Expected: all selected tests pass.

---

### Task 6: Update Documentation And Final Validation

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Optional regenerate: `frontend/src/lib/api-types.ts`

- [ ] **Step 1: Update README structure notes**

In `README.md`, update the domain list so:

```text
domains/garmin_health/ owns canonical Garmin health contracts and daily metric composition used by parser, ingest persistence, analytics, experiments, and assistant.
domains/garmin_analytics/ owns Garmin-derived read models, dashboard data, raw endpoint responses, insights, analyses, and period summaries.
```

- [ ] **Step 2: Update architecture docs**

In `docs/ARCHITECTURE.md`, document this dependency direction:

```text
parser and infra/database -> garmin_health, app.utils
garmin_analytics -> garmin_health, app.utils
experiments and assistant -> garmin_health contracts, and analytics adapters only when loading analytics read data
garmin_health -> app.contracts.base, app.utils
app.utils -> stdlib + numpy only
```

Update the existing Project Layout / aggregates references:
- Replace `domains/garmin_analytics/domain/aggregates/` bullet (line 64) with a `domains/garmin_health/` description matching the boundaries section above.
- In the `garmin_analytics` slice description, drop the `utils.py owns daily aggregate composition shared by ingest persistence` clause and the `domain/primitives/` claim of "generic numeric/window helpers" (only window/timestamps/trends remain).
- Confirm the "Shared Utilities" section already exists (added in this same PR — see ARCHITECTURE.md). If not, add it.

Also remove any wording that says daily aggregate composition is shared from `garmin_analytics/utils.py`.

- [ ] **Step 3: Run full backend validation**

Run:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

Expected:
- Ruff reports `All checks passed!`
- Pyright reports `0 errors, 0 warnings, 0 informations`
- Pytest reports all tests passing

- [ ] **Step 4: Check OpenAPI-generated types**

This refactor is import-path-only — no model fields change, no response shapes change. The generated TypeScript must therefore be either byte-identical or differ only in schema ordering (FastAPI keys component schemas by class name, which is unchanged).

Run:

```bash
bash scripts/generate-api-types.sh
git diff -- frontend/src/lib/api-types.ts
```

Expected: empty diff or pure ordering churn. **If any field, type, or schema name changes, stop — that means a contract leaked across the move.** Investigate before committing. If diff is ordering-only, commit the regenerated file and run:

```bash
cd frontend && npm run check
```

Expected: frontend check passes.

This is also a parser-import-path change with no parsing semantics altered, so the `reingest.py` script does **not** need to be re-run. Do not re-ingest as part of this refactor.

- [ ] **Step 5: Inspect final dependency state**

Run:

```bash
rg -n "garmin_analytics\\.utils|garmin_analytics\\.domain\\.aggregates\\.daily|compute_daily_aggregates|DailyAggregatesResponse" backend/app/infra backend/app/domains/garmin_health backend/app/domains/garmin_analytics -g '*.py'
```

Expected:
- No `garmin_analytics.utils` matches.
- No `garmin_analytics.domain.aggregates.daily` matches.
- No `compute_daily_aggregates` matches.
- `DailyAggregatesResponse` appears only under analytics contracts, routes, application response wrapping, or tests.

Run:

```bash
rg -n "app\\.domains\\.garmin_analytics\\.contracts" backend/app backend/tests -g '*.py'
```

Expected: remaining matches import analytics-owned response DTOs only. There should be no remaining imports of `DailyMetric`, `DailyMetricStats`, `DailyHeartRateStats`, `HRZoneBucket`, `DayData`, `DayWellness`, `DaySleep`, `DayHrv`, `DaySkinTemp`, or individual reading row models from `app.domains.garmin_analytics.contracts`.

Also confirm no domain owns the moved numeric helpers:

```bash
rg -n "domains/garmin_(health|analytics)/.*numeric" backend/app -g '*.py' --files-with-matches
rg -n "from app\\.domains\\.garmin_analytics\\.domain\\.primitives\\.numeric" backend -g '*.py'
```

Expected: both produce no matches. Numeric helpers should resolve only to `app.utils.numeric`.
