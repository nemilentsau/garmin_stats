# Garmin Analytics Concern Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Garmin analytics into concern-based domain/application packages while preserving API behavior and adding characterization tests before analytics function splits.

**Architecture:** Keep `application/` as thin orchestration over repositories, cache keys, selected-date behavior, and existing response assembly. Move pure calculations into `domain/primitives`, `domain/aggregates`, `domain/analysis`, and `domain/insights`. Add architecture guardrails so future analytics code cannot quietly reintroduce infra/cache/repository dependencies into pure domain modules.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, ruff, pyright, numpy.

---

## Source Spec

Implement the approved spec:

`docs/superpowers/specs/2026-05-06-garmin-analytics-concern-layout-design.md`

Do not change API schemas, routes, model fields, or frontend code.

## File Structure

Create these packages:

- `backend/app/domains/garmin_analytics/domain/primitives/__init__.py`
- `backend/app/domains/garmin_analytics/domain/primitives/numeric.py`
- `backend/app/domains/garmin_analytics/domain/primitives/trends.py`
- `backend/app/domains/garmin_analytics/domain/aggregates/__init__.py`
- `backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py`
- `backend/app/domains/garmin_analytics/domain/aggregates/daily.py`
- `backend/app/domains/garmin_analytics/domain/aggregates/period.py`
- `backend/app/domains/garmin_analytics/domain/analysis/__init__.py`
- `backend/app/domains/garmin_analytics/domain/analysis/body_battery.py`
- `backend/app/domains/garmin_analytics/domain/analysis/heart_rate.py`
- `backend/app/domains/garmin_analytics/domain/analysis/hrv.py`
- `backend/app/domains/garmin_analytics/domain/analysis/sleep.py`
- `backend/app/domains/garmin_analytics/domain/analysis/stress.py`
- `backend/app/domains/garmin_analytics/domain/insights/__init__.py`
- `backend/app/domains/garmin_analytics/domain/insights/heart_rate.py`
- `backend/app/domains/garmin_analytics/domain/insights/hrv.py`

Update these application files:

- `backend/app/domains/garmin_analytics/application/biometrics.py`
- `backend/app/domains/garmin_analytics/application/analysis.py` (create)
- `backend/app/domains/garmin_analytics/application/insights.py`
- `backend/app/domains/garmin_analytics/application/overview.py`
- `backend/app/domains/garmin_analytics/application/period_summary.py`

Delete these application files after their content moves:

- `backend/app/domains/garmin_analytics/application/biometric_responses.py`
- `backend/app/domains/garmin_analytics/application/body_battery_analysis.py`
- `backend/app/domains/garmin_analytics/application/daily_aggregates.py`
- `backend/app/domains/garmin_analytics/application/heart_rate_analysis.py`
- `backend/app/domains/garmin_analytics/application/hrv_analysis.py`
- `backend/app/domains/garmin_analytics/application/numeric.py`
- `backend/app/domains/garmin_analytics/application/period_aggregates.py`
- `backend/app/domains/garmin_analytics/application/sleep_analysis.py`
- `backend/app/domains/garmin_analytics/application/stress_analysis.py`
- `backend/app/domains/garmin_analytics/application/trends.py`

Tests:

- Modify `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`
- Modify `backend/tests/architecture/test_architecture_global_ownership.py`
- Modify `backend/tests/domains/garmin_analytics/test_stats.py`
- Modify `backend/tests/domains/garmin_analytics/test_heart_rate_analysis.py`
- Modify `backend/tests/domains/garmin_analytics/test_heart_rate_service.py`
- Modify `backend/tests/domains/garmin_analytics/test_hrv_service.py`
- Add `backend/tests/domains/garmin_analytics/test_period_aggregates.py`

## Task 1: Add Garmin Analytics Domain Boundary Guardrails

**Files:**
- Modify: `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`

- [ ] **Step 1: Add failing domain-boundary architecture tests**

Append these tests to `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`:

```python
def test_garmin_analytics_domain_modules_do_not_import_application_or_infra():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/garmin_analytics/domain").rglob("*.py")
    ]
    assert_no_text_in_files(
        paths,
        [
            "app.domains.garmin_analytics.application",
            "app.domains.garmin_analytics.infra",
            "app.infra",
            "fastapi",
        ],
    )


def test_garmin_analytics_analysis_modules_do_not_import_insights():
    analysis_root = REPO_ROOT / "backend/app/domains/garmin_analytics/domain/analysis"
    if not analysis_root.exists():
        return
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in analysis_root.rglob("*.py")
    ]
    assert_no_text_in_files(paths, ["app.domains.garmin_analytics.domain.insights"])
```

- [ ] **Step 2: Run architecture tests**

Run:

```bash
cd backend && uv run pytest tests/architecture/test_architecture_garmin_analytics_boundaries.py -v
```

Expected: pass. These tests are guardrails for future moves. They do not fail yet because the target subpackages do not exist.

## Task 2: Move Primitives And Aggregate Modules To Domain

**Files:**
- Create: `backend/app/domains/garmin_analytics/domain/primitives/__init__.py`
- Create: `backend/app/domains/garmin_analytics/domain/aggregates/__init__.py`
- Move: `backend/app/domains/garmin_analytics/application/numeric.py` -> `backend/app/domains/garmin_analytics/domain/primitives/numeric.py`
- Move: `backend/app/domains/garmin_analytics/application/trends.py` -> `backend/app/domains/garmin_analytics/domain/primitives/trends.py`
- Move: `backend/app/domains/garmin_analytics/domain/windows.py` -> `backend/app/domains/garmin_analytics/domain/primitives/windows.py`
- Move: `backend/app/domains/garmin_analytics/application/biometric_responses.py` -> `backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py`
- Move: `backend/app/domains/garmin_analytics/application/daily_aggregates.py` -> `backend/app/domains/garmin_analytics/domain/aggregates/daily.py`
- Move: `backend/app/domains/garmin_analytics/application/period_aggregates.py` -> `backend/app/domains/garmin_analytics/domain/aggregates/period.py`
- Modify: imports in Garmin analytics app/tests/database.

- [ ] **Step 1: Verify existing characterization tests before moving**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py -v
```

Expected: pass. These tests characterize primitives, biometric response flattening, daily aggregate behavior, HR zones, and current period summary behavior.

- [ ] **Step 2: Move files with `git mv`**

Run:

```bash
git mv backend/app/domains/garmin_analytics/application/numeric.py backend/app/domains/garmin_analytics/domain/primitives/numeric.py
git mv backend/app/domains/garmin_analytics/application/trends.py backend/app/domains/garmin_analytics/domain/primitives/trends.py
git mv backend/app/domains/garmin_analytics/domain/windows.py backend/app/domains/garmin_analytics/domain/primitives/windows.py
git mv backend/app/domains/garmin_analytics/application/biometric_responses.py backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py
git mv backend/app/domains/garmin_analytics/application/daily_aggregates.py backend/app/domains/garmin_analytics/domain/aggregates/daily.py
git mv backend/app/domains/garmin_analytics/application/period_aggregates.py backend/app/domains/garmin_analytics/domain/aggregates/period.py
```

Create empty package markers:

```python
# backend/app/domains/garmin_analytics/domain/primitives/__init__.py
```

```python
# backend/app/domains/garmin_analytics/domain/aggregates/__init__.py
```

- [ ] **Step 3: Update imports**

Replace imports as follows:

```python
from .numeric import ...
```

becomes:

```python
from app.domains.garmin_analytics.domain.primitives.numeric import ...
```

```python
from .trends import ...
```

becomes:

```python
from app.domains.garmin_analytics.domain.primitives.trends import ...
```

```python
from .daily_aggregates import ...
```

becomes:

```python
from app.domains.garmin_analytics.domain.aggregates.daily import ...
```

```python
from .period_aggregates import compute_period_summary
```

becomes:

```python
from app.domains.garmin_analytics.domain.aggregates.period import compute_period_summary
```

```python
from .biometric_responses import ...
```

becomes:

```python
from app.domains.garmin_analytics.domain.aggregates.biometric_responses import ...
```

```python
from app.domains.garmin_analytics.domain.windows import compute_windows
```

becomes:

```python
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
```

Update all matching imports under:

- `backend/app/domains/garmin_analytics/application/`
- `backend/app/infra/database.py`
- `backend/tests/domains/garmin_analytics/`

- [ ] **Step 4: Update global ownership allowlists**

In `backend/tests/architecture/test_architecture_global_ownership.py`, replace moved application paths in `ALLOWLISTED_APP_MODELS_IMPORTERS` with their new domain paths:

```python
"backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py",
"backend/app/domains/garmin_analytics/domain/aggregates/daily.py",
"backend/app/domains/garmin_analytics/domain/aggregates/period.py",
"backend/app/domains/garmin_analytics/domain/primitives/trends.py",
```

Remove old paths:

```python
"backend/app/domains/garmin_analytics/application/biometric_responses.py",
"backend/app/domains/garmin_analytics/application/daily_aggregates.py",
"backend/app/domains/garmin_analytics/application/period_aggregates.py",
"backend/app/domains/garmin_analytics/application/trends.py",
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py tests/architecture -v
```

Expected: pass.

## Task 3: Add Period Summary Helper Characterization Tests

**Files:**
- Add: `backend/tests/domains/garmin_analytics/test_period_aggregates.py`

- [ ] **Step 1: Add helper-level tests before production decomposition**

Create `backend/tests/domains/garmin_analytics/test_period_aggregates.py` with this content:

```python
"""Tests for Garmin analytics period aggregate helper policies."""

from app.domains.garmin_analytics.domain.aggregates.period import (
    compute_period_body_battery,
    compute_period_heart_rate,
    compute_period_hrv,
    compute_period_respiration,
    compute_period_skin_temp,
    compute_period_sleep,
    compute_period_spo2,
    compute_period_stress,
)
from app.models import (
    BodyBatteryReading,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvSummary,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SpO2Reading,
    StressReading,
)


def _day(
    date: str = "2026-01-15",
    *,
    heart_rate: list[int] | None = None,
    resting_hr: list[RestingHRReading] | None = None,
    stress: list[int] | None = None,
    respiration: list[float] | None = None,
    spo2: list[int] | None = None,
    body_battery: list[int] | None = None,
    hrv_summaries: list[HrvSummary] | None = None,
    skin_temp: list[SkinTempOvernight] | None = None,
    sleep: list[SleepAssessment] | None = None,
) -> DayData:
    return DayData(
        date=date,
        wellness=DayWellness(
            date=date,
            heart_rate=[
                HeartRateReading(timestamp=f"{date}T00:{i:02d}:00", value=value)
                for i, value in enumerate(heart_rate or [])
            ],
            resting_hr=resting_hr or [],
            stress=[
                StressReading(timestamp=f"{date}T01:{i:02d}:00", value=value)
                for i, value in enumerate(stress or [])
            ],
            respiration=[
                RespirationReading(timestamp=f"{date}T02:{i:02d}:00", value=value)
                for i, value in enumerate(respiration or [])
            ],
            spo2=[
                SpO2Reading(timestamp=f"{date}T03:{i:02d}:00", value=value)
                for i, value in enumerate(spo2 or [])
            ],
            body_battery=[
                BodyBatteryReading(timestamp=f"{date}T04:{i:02d}:00", value=value)
                for i, value in enumerate(body_battery or [])
            ],
        ),
        hrv=DayHrv(date=date, hrv_summaries=hrv_summaries or []),
        skin_temp=DaySkinTemp(date=date, skin_temp_overnight=skin_temp or []),
        sleep=DaySleep(date=date, sleep_assessments=sleep or []),
    )
```

Then add tests for the required matrix:

```python
def test_period_heart_rate_empty_days_return_nulls_and_empty_zones():
    result = compute_period_heart_rate([])
    assert result.avg is None
    assert result.avg_resting is None
    assert result.typical_low is None
    assert result.typical_high is None
    assert result.zones == []


def test_period_heart_rate_uses_raw_reading_weighted_average_and_resting_last_value():
    day1 = _day(
        "2026-01-01",
        heart_rate=[60, 60, 60, 60, 60],
        resting_hr=[
            RestingHRReading(timestamp="2026-01-01T05:00:00", resting_hr=52),
            RestingHRReading(timestamp="2026-01-01T06:00:00", resting_hr=48),
        ],
    )
    day2 = _day(
        "2026-01-02",
        heart_rate=[100],
        resting_hr=[
            RestingHRReading(
                timestamp="2026-01-02T06:00:00",
                resting_hr=51,
                current_day_resting_hr=46,
            )
        ],
    )
    result = compute_period_heart_rate([day1, day2])
    assert result.avg == 66.7
    assert result.avg_resting == 47.0
    assert result.zones


def test_period_stress_empty_days_return_nulls():
    result = compute_period_stress([])
    assert result.avg is None
    assert result.typical_low is None
    assert result.typical_high is None


def test_period_stress_uses_raw_values_for_average_and_percentiles():
    result = compute_period_stress([_day(stress=[10, 20, 30, 40])])
    assert result.avg == 25.0
    assert result.typical_low == 17.5
    assert result.typical_high == 32.5


def test_period_respiration_empty_days_return_nulls():
    result = compute_period_respiration([])
    assert result.avg is None
    assert result.typical_low is None
    assert result.typical_high is None


def test_period_respiration_uses_raw_values_for_average_and_percentiles():
    result = compute_period_respiration([_day(respiration=[12.0, 14.0, 16.0, 18.0])])
    assert result.avg == 15.0
    assert result.typical_low == 13.5
    assert result.typical_high == 16.5


def test_period_hrv_empty_summaries_return_nulls_and_zero_days():
    result = compute_period_hrv([_day()])
    assert result.avg_nightly is None
    assert result.avg_weekly is None
    assert result.balanced_pct is None
    assert result.total_days == 0


def test_period_hrv_excludes_null_values_and_rounds_balanced_status_percentage():
    result = compute_period_hrv([
        _day(
            "2026-01-01",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-01",
                    last_night_average=50.0,
                    weekly_average=None,
                    status="balanced",
                )
            ],
        ),
        _day(
            "2026-01-02",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-02",
                    last_night_average=None,
                    weekly_average=60.0,
                    status="low",
                )
            ],
        ),
        _day(
            "2026-01-03",
            hrv_summaries=[
                HrvSummary(
                    date="2026-01-03",
                    last_night_average=70.0,
                    weekly_average=80.0,
                    status="balanced",
                )
            ],
        ),
    ])
    assert result.avg_nightly == 60.0
    assert result.avg_weekly == 70.0
    assert result.balanced_pct == 67
    assert result.total_days == 3


def test_period_spo2_empty_readings_return_nulls_and_zero_counts():
    result = compute_period_spo2([])
    assert result.avg is None
    assert result.lowest_min is None
    assert result.low_days == 0
    assert result.total_days == 0


def test_period_spo2_low_threshold_and_lowest_min_use_daily_mins():
    result = compute_period_spo2([
        _day("2026-01-01", spo2=[95, 89]),
        _day("2026-01-02", spo2=[90, 92]),
    ])
    assert result.avg == 91.5
    assert result.lowest_min == 89.0
    assert result.low_days == 1
    assert result.total_days == 2


def test_period_skin_temp_empty_records_return_nulls_and_zero_days():
    result = compute_period_skin_temp([])
    assert result.avg_deviation is None
    assert result.max_deviation is None
    assert result.min_deviation is None
    assert result.avg_nightly is None
    assert result.days_tracked == 0


def test_period_skin_temp_excludes_null_deviations_and_averages_nightly_values():
    result = compute_period_skin_temp([
        _day(
            "2026-01-01",
            skin_temp=[
                SkinTempOvernight(
                    date="2026-01-01",
                    average_deviation=-0.234,
                    nightly_value=36.4,
                ),
            ],
        ),
        _day(
            "2026-01-02",
            skin_temp=[
                SkinTempOvernight(
                    date="2026-01-02",
                    average_deviation=None,
                    nightly_value=36.8,
                ),
            ],
        ),
    ])
    assert result.avg_deviation == -0.2
    assert result.min_deviation == -0.23
    assert result.max_deviation == -0.23
    assert result.avg_nightly == 36.6
    assert result.days_tracked == 1


def test_period_sleep_empty_assessments_return_nulls_and_zero_days():
    result = compute_period_sleep([])
    assert result.avg_score is None
    assert result.avg_deep_score is None
    assert result.days_tracked == 0


def test_period_sleep_excludes_null_overall_and_deep_scores_independently():
    result = compute_period_sleep([
        _day(
            "2026-01-01",
            sleep=[
                SleepAssessment(date="2026-01-01", overall_score=80, deep_sleep_score=None),
            ],
        ),
        _day(
            "2026-01-02",
            sleep=[
                SleepAssessment(date="2026-01-02", overall_score=None, deep_sleep_score=70),
            ],
        ),
    ])
    assert result.avg_score == 80.0
    assert result.avg_deep_score == 70.0
    assert result.days_tracked == 1


def test_period_body_battery_empty_readings_return_nulls_and_zero_days():
    result = compute_period_body_battery([])
    assert result.avg_min is None
    assert result.avg_max is None
    assert result.days_tracked == 0


def test_period_body_battery_averages_each_days_min_and_max():
    result = compute_period_body_battery([
        _day("2026-01-01", body_battery=[20, 80]),
        _day("2026-01-02", body_battery=[40, 60]),
    ])
    assert result.avg_min == 30.0
    assert result.avg_max == 70.0
    assert result.days_tracked == 2
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_period_aggregates.py -v
```

Expected: fail during import with missing names such as `compute_period_heart_rate`. This proves the new helper-level tests are not accidentally testing existing public behavior.

## Task 4: Decompose Period Aggregates

**Files:**
- Modify: `backend/app/domains/garmin_analytics/domain/aggregates/period.py`
- Test: `backend/tests/domains/garmin_analytics/test_period_aggregates.py`
- Test: `backend/tests/domains/garmin_analytics/test_stats.py`

- [ ] **Step 1: Add period helper functions**

In `backend/app/domains/garmin_analytics/domain/aggregates/period.py`, split the current `compute_period_summary` logic into:

```python
def compute_period_heart_rate(days: list[DayData]) -> PeriodHeartRateStats: ...
def compute_period_stress(days: list[DayData]) -> PeriodMetricStats: ...
def compute_period_respiration(days: list[DayData]) -> PeriodMetricStats: ...
def compute_period_hrv(days: list[DayData]) -> PeriodHrvStats: ...
def compute_period_spo2(days: list[DayData]) -> PeriodSpo2Stats: ...
def compute_period_skin_temp(days: list[DayData]) -> PeriodSkinTempStats: ...
def compute_period_sleep(days: list[DayData]) -> PeriodSleepStats: ...
def compute_period_body_battery(days: list[DayData]) -> PeriodBodyBatteryStats: ...
```

Then rewrite `compute_period_summary` as:

```python
def compute_period_summary(days: list[DayData]) -> PeriodSummary:
    """Compute period-level stats from raw per-day data."""
    return PeriodSummary(
        heart_rate=compute_period_heart_rate(days),
        stress=compute_period_stress(days),
        respiration=compute_period_respiration(days),
        hrv=compute_period_hrv(days),
        spo2=compute_period_spo2(days),
        skin_temp=compute_period_skin_temp(days),
        sleep=compute_period_sleep(days),
        body_battery=compute_period_body_battery(days),
    )
```

- [ ] **Step 2: Run period tests and verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_period_aggregates.py tests/domains/garmin_analytics/test_stats.py -v
```

Expected: pass.

## Task 5: Split Simple Tab Analysis Calculators From Application Cache Wrappers

**Files:**
- Create: `backend/app/domains/garmin_analytics/domain/analysis/__init__.py`
- Create: `backend/app/domains/garmin_analytics/domain/analysis/sleep.py`
- Create: `backend/app/domains/garmin_analytics/domain/analysis/stress.py`
- Create: `backend/app/domains/garmin_analytics/domain/analysis/body_battery.py`
- Create: `backend/app/domains/garmin_analytics/application/analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/insights.py`
- Delete: `backend/app/domains/garmin_analytics/application/sleep_analysis.py`
- Delete: `backend/app/domains/garmin_analytics/application/stress_analysis.py`
- Delete: `backend/app/domains/garmin_analytics/application/body_battery_analysis.py`

- [ ] **Step 1: Verify existing characterization tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py -v
```

Expected: pass. These tests characterize the current route-facing sleep/body/stress analysis behavior through application functions.

- [ ] **Step 2: Move pure calculators**

Create `backend/app/domains/garmin_analytics/domain/analysis/sleep.py` with pure functions moved from `application/sleep_analysis.py`:

```python
def compute_sleep_trend(metrics: list[DailyMetric]) -> list[SleepTrendPoint]: ...
def compute_weekly_sleep_boxplots(metrics: list[DailyMetric]) -> list[WeeklySleepBox]: ...
def compute_sleep_analysis(metrics: list[DailyMetric]) -> SleepAnalysisResponse: ...
```

Create `backend/app/domains/garmin_analytics/domain/analysis/stress.py` with:

```python
def compute_stress_trend(metrics: list[DailyMetric]) -> list[StressTrendPoint]: ...
def compute_weekly_stress_boxplots(metrics: list[DailyMetric]) -> list[WeeklyStressBox]: ...
def compute_stress_analysis(metrics: list[DailyMetric]) -> StressAnalysisResponse: ...
```

Create `backend/app/domains/garmin_analytics/domain/analysis/body_battery.py` with:

```python
def compute_body_battery_trend(metrics: list[DailyMetric]) -> list[BodyBatteryTrendPoint]: ...
def compute_weekly_body_battery_boxplots(metrics: list[DailyMetric]) -> list[WeeklyBodyBatteryBox]: ...
def compute_body_battery_analysis(metrics: list[DailyMetric]) -> BodyBatteryAnalysisResponse: ...
```

Use imports from:

```python
from app.domains.garmin_analytics.domain.primitives.numeric import safe_percentile
from app.domains.garmin_analytics.domain.primitives.trends import group_by_iso_week, trailing_ma7
```

- [ ] **Step 3: Create application analysis wrappers**

Create `backend/app/domains/garmin_analytics/application/analysis.py`:

```python
"""Analysis use cases for Garmin analytics."""

from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.domains.garmin_analytics.domain.analysis.body_battery import (
    compute_body_battery_analysis,
)
from app.domains.garmin_analytics.domain.analysis.sleep import compute_sleep_analysis
from app.domains.garmin_analytics.domain.analysis.stress import compute_stress_analysis
from app.infra import cache
from app.models import (
    BodyBatteryAnalysisResponse,
    SleepAnalysisResponse,
    StressAnalysisResponse,
)


def load_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return cache.cached(
        cache.SLEEP_ANALYSIS,
        lambda: compute_sleep_analysis(repo.load_daily_metrics()),
    )


def load_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    return cache.cached(
        cache.STRESS_ANALYSIS,
        lambda: compute_stress_analysis(repo.load_daily_metrics()),
    )


def load_body_battery_analysis(
    repo: BiometricReadRepository,
) -> BodyBatteryAnalysisResponse:
    return cache.cached(
        cache.BODY_BATTERY_ANALYSIS,
        lambda: compute_body_battery_analysis(repo.load_daily_metrics()),
    )
```

- [ ] **Step 4: Retarget application facade**

In `backend/app/domains/garmin_analytics/application/insights.py`, replace imports for sleep/stress/body battery analysis with imports from `application.analysis`.

Keep public function names unchanged:

```python
def get_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return analysis.load_sleep_analysis(repo)
```

Apply the same pattern for stress and body battery.

- [ ] **Step 5: Delete old application analysis files**

Delete:

```bash
git rm backend/app/domains/garmin_analytics/application/sleep_analysis.py
git rm backend/app/domains/garmin_analytics/application/stress_analysis.py
git rm backend/app/domains/garmin_analytics/application/body_battery_analysis.py
```

- [ ] **Step 6: Update allowlists and verify**

Update `backend/tests/architecture/test_architecture_global_ownership.py`:

- remove deleted application analysis files from `ALLOWLISTED_APP_MODELS_IMPORTERS`
- add new domain analysis files to `ALLOWLISTED_APP_MODELS_IMPORTERS`
- remove deleted files from `ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS`
- add `backend/app/domains/garmin_analytics/application/analysis.py` to `ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS`

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py tests/architecture -v
```

Expected: pass.

## Task 6: Move Heart Rate Analysis Calculators

**Files:**
- Create: `backend/app/domains/garmin_analytics/domain/analysis/heart_rate.py`
- Modify: `backend/app/domains/garmin_analytics/application/analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/insights.py`
- Delete: `backend/app/domains/garmin_analytics/application/heart_rate_analysis.py`
- Test: `backend/tests/domains/garmin_analytics/test_heart_rate_analysis.py`

- [ ] **Step 1: Verify existing characterization tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_heart_rate_analysis.py -v
```

Expected: pass. These tests characterize circadian profile, sleeping HR trend, resting HR moving average, histogram binning, and weekly boxplot behavior.

- [ ] **Step 2: Move pure calculators**

Move pure functions from `application/heart_rate_analysis.py` to `domain/analysis/heart_rate.py`:

```python
def compute_circadian_profile(days: list[DayWellness]) -> list[CircadianHRPoint]: ...
def compute_sleeping_hr_trend(days: list[DaySleep]) -> list[SleepingHRPoint]: ...
def compute_resting_hr_trend(metrics: list[DailyMetric]) -> list[RestingHRTrendPoint]: ...
def compute_daily_avg_trend(metrics: list[DailyMetric]) -> list[DailyAvgHRTrendPoint]: ...
def compute_hr_distribution(days: list[DayWellness]) -> HRDistributionResponse: ...
def compute_weekly_resting_hr_boxplots(metrics: list[DailyMetric]) -> list[WeeklyRestingHRBox]: ...
def compute_heart_rate_analysis(
    all_wellness: list[DayWellness],
    all_sleep: list[DaySleep],
    metrics: list[DailyMetric],
) -> HeartRateAnalysisResponse: ...
```

Keep `compute_windows` usage in the domain analysis module because it is now a domain primitive under `domain.primitives.windows`.

- [ ] **Step 3: Add application wrappers**

In `application/analysis.py`, add:

```python
def load_heart_rate_analysis(repo: BiometricReadRepository) -> HeartRateAnalysisResponse:
    return cache.cached(
        cache.HR_ANALYSIS,
        lambda: compute_heart_rate_analysis(
            repo.load_wellness(),
            repo.load_sleep(),
            repo.load_daily_metrics(),
        ),
    )


def load_hr_distribution(
    repo: BiometricReadRepository,
    date: str,
) -> HRDistributionResponse:
    wellness_days = repo.load_wellness(date)
    if not wellness_days:
        raise LookupError(f"No heart-rate data found for {date}")
    return compute_hr_distribution(wellness_days)
```

- [ ] **Step 4: Retarget facade and tests**

In `application/insights.py`, route `get_heart_rate_analysis` and `get_hr_distribution` through `application.analysis`.

In `backend/tests/domains/garmin_analytics/test_heart_rate_analysis.py`, update imports from `application.heart_rate_analysis` to `domain.analysis.heart_rate`.

- [ ] **Step 5: Delete old file, update allowlists, verify**

Delete:

```bash
git rm backend/app/domains/garmin_analytics/application/heart_rate_analysis.py
```

Update global ownership allowlists for moved model/cache imports.

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_heart_rate_analysis.py tests/domains/garmin_analytics/test_heart_rate_service.py tests/architecture -v
```

Expected: pass.

## Task 7: Split HRV Analysis From HRV Insights

**Files:**
- Create: `backend/app/domains/garmin_analytics/domain/analysis/hrv.py`
- Create: `backend/app/domains/garmin_analytics/domain/insights/__init__.py`
- Create: `backend/app/domains/garmin_analytics/domain/insights/hrv.py`
- Modify: `backend/app/domains/garmin_analytics/application/analysis.py`
- Modify: `backend/app/domains/garmin_analytics/application/insights.py`
- Delete: `backend/app/domains/garmin_analytics/application/hrv_analysis.py`
- Delete: `backend/app/domains/garmin_analytics/application/hrv.py`
- Test: `backend/tests/domains/garmin_analytics/test_hrv_service.py`

- [ ] **Step 1: Verify existing characterization tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_hrv_service.py -v
```

Expected: pass. These tests characterize HRV insights, quality, status streaks, long baseline, baseline bands, distribution, trajectory, and day-of-week buckets.

- [ ] **Step 2: Move analysis-only functions**

Move these functions from `application/hrv.py` to `domain/analysis/hrv.py` and rename them without leading underscores:

```python
def compute_hrv_distribution(metrics: list[DailyMetric]) -> HrvDistribution | None: ...
def compute_trajectory(hrv_values: list[HrvValue]) -> HrvTrajectory | None: ...
def compute_day_of_week(metrics: list[DailyMetric]) -> list[HrvDayOfWeekBucket]: ...
def extract_baseline_bands(day_rows: list[DayHrv]) -> HrvBaselineBands | None: ...
```

Move functions from `application/hrv_analysis.py` to `domain/analysis/hrv.py`:

```python
def compute_nightly_hrv_trend(metrics: list[DailyMetric]) -> list[NightlyHrvTrendPoint]: ...
def compute_weekly_hrv_boxplots(metrics: list[DailyMetric]) -> list[WeeklyHrvBox]: ...
def compute_pattern_window(metrics: list[DailyMetric]) -> HrvPatternWindow: ...
def compute_pattern_windows(metrics: list[DailyMetric]) -> dict[str, HrvPatternWindow]: ...
def compute_hrv_analysis(metrics: list[DailyMetric]) -> HrvAnalysisResponse: ...
```

- [ ] **Step 3: Move insight functions**

Move insight functions from `application/hrv.py` to `domain/insights/hrv.py`:

```python
def compute_recovery(metrics: list[DailyMetric], selected_index: int) -> HrvRecovery: ...
def compute_quality(hrv_values: list[HrvValue]) -> HrvDataQuality: ...
def build_intraday_segment(hrv_values: list[HrvValue]) -> HrvIntradaySegment | None: ...
def compute_trend_band(nightly_vals: list[float]) -> HrvTrendBand: ...
def compute_status_mix(metrics: list[DailyMetric], selected_index: int) -> list[HrvStatusBucket]: ...
def compute_streak(metrics: list[DailyMetric], selected_index: int) -> HrvStreak: ...
def compute_long_baseline(metrics: list[DailyMetric], selected_index: int) -> HrvLongBaseline | None: ...
def resting_delta_vs_recent(metrics: list[DailyMetric], selected_index: int) -> float | None: ...
def build_insights(ctx: InsightContext) -> list[HrvInsight]: ...
def compute_hrv_insights(
    metrics: list[DailyMetric],
    selected_date: str | None,
    day_rows: list[DayHrv],
) -> HrvInsightsResponse: ...
```

Use a public dataclass `InsightContext` in the domain insights module.

The domain insights module may import pure analysis helpers from `domain.analysis.hrv`:

```python
from app.domains.garmin_analytics.domain.analysis.hrv import (
    compute_day_of_week,
    compute_hrv_distribution,
    compute_trajectory,
    extract_baseline_bands,
)
```

- [ ] **Step 4: Add application wrappers**

In `application/analysis.py`, add:

```python
def load_hrv_analysis(repo: BiometricReadRepository) -> HrvAnalysisResponse:
    return cache.cached(
        cache.HRV_ANALYSIS,
        lambda: compute_hrv_analysis(repo.load_daily_metrics()),
    )
```

In `application/insights.py`, implement `get_hrv_insights` as orchestration:

```python
def get_hrv_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HrvInsightsResponse:
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No daily metrics available")
    selected_date = date or metrics[-1].date
    day_rows = repo.load_hrv(selected_date)
    return compute_hrv_insights(metrics, selected_date, day_rows)
```

Keep the existing missing-date error behavior from `application/hrv.py` when moving this wrapper.

- [ ] **Step 5: Retarget tests**

In `backend/tests/domains/garmin_analytics/test_hrv_service.py`, update imports:

- analysis helper tests import from `domain.analysis.hrv`
- insight helper tests import from `domain.insights.hrv`
- application use-case tests import `get_hrv_insights` through `application.insights` if route-facing orchestration is being tested

- [ ] **Step 6: Delete old files, update allowlists, verify**

Delete:

```bash
git rm backend/app/domains/garmin_analytics/application/hrv.py
git rm backend/app/domains/garmin_analytics/application/hrv_analysis.py
```

Update global ownership allowlists for new domain files and removed application files.

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_hrv_service.py tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py tests/architecture -v
```

Expected: pass.

## Task 8: Split Heart Rate Insight Rules

**Files:**
- Create: `backend/app/domains/garmin_analytics/domain/insights/heart_rate.py`
- Modify: `backend/app/domains/garmin_analytics/application/insights.py`
- Delete: `backend/app/domains/garmin_analytics/application/heart_rate.py`
- Test: `backend/tests/domains/garmin_analytics/test_heart_rate_service.py`

- [ ] **Step 1: Verify existing characterization tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_heart_rate_service.py -v
```

Expected: pass.

- [ ] **Step 2: Move pure insight rules**

Move from `application/heart_rate.py` to `domain/insights/heart_rate.py`:

```python
def zone_for_value(value: int) -> tuple[str, int, int | None] | None: ...
def estimate_default_interval_minutes(readings: list[tuple[datetime, int]]) -> float: ...
def compute_zone_minutes(hr_readings: list[HeartRateReading]) -> list[HRZoneDuration]: ...
def compute_recovery(metrics: list[DailyMetric], selected_index: int) -> HeartRateRecovery: ...
def build_insights(
    metrics: list[DailyMetric],
    selected_index: int,
    recovery: HeartRateRecovery,
    quality: HeartRateDataQuality,
) -> list[HeartRateInsight]: ...
def compute_heart_rate_insights(
    metrics: list[DailyMetric],
    selected_date: str | None,
    wellness_days: list[DayWellness],
) -> HeartRateInsightsResponse: ...
```

- [ ] **Step 3: Add application wrapper**

In `application/insights.py`, implement `get_heart_rate_insights` as orchestration:

```python
def get_heart_rate_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HeartRateInsightsResponse:
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No daily metrics available")
    selected_date = date or metrics[-1].date
    wellness_days = repo.load_wellness(selected_date)
    return compute_heart_rate_insights(metrics, selected_date, wellness_days)
```

Keep the existing missing-date behavior from `application/heart_rate.py` when moving this wrapper.

- [ ] **Step 4: Retarget tests**

In `backend/tests/domains/garmin_analytics/test_heart_rate_service.py`, update imports to target:

```python
from app.domains.garmin_analytics.application.insights import get_heart_rate_insights
```

or domain insight helper imports when testing pure functions directly.

- [ ] **Step 5: Delete old file, update allowlists, verify**

Delete:

```bash
git rm backend/app/domains/garmin_analytics/application/heart_rate.py
```

Update global ownership allowlists.

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_heart_rate_service.py tests/architecture -v
```

Expected: pass.

## Task 9: Final Architecture Cleanup And Validation

**Files:**
- Modify: `backend/tests/architecture/test_architecture_global_ownership.py`
- Modify: `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`
- Modify: all files changed by Tasks 1-8.

- [ ] **Step 1: Confirm old application modules are gone**

Run:

```bash
rg -n "application\\.(numeric|trends|biometric_responses|daily_aggregates|period_aggregates|sleep_analysis|stress_analysis|body_battery_analysis|heart_rate_analysis|hrv_analysis|heart_rate|hrv)" backend/app backend/tests
```

Expected: no matches except plan/spec text if the search includes docs. For this command, it should search only `backend/app backend/tests`, so no matches.

- [ ] **Step 2: Confirm domain modules have no forbidden imports**

Run:

```bash
cd backend && uv run pytest tests/architecture -v
```

Expected: pass.

- [ ] **Step 3: Run backend lint**

Run:

```bash
cd backend && uv run ruff check app/ tests/
```

Expected: `All checks passed!`

- [ ] **Step 4: Run backend type check**

Run:

```bash
cd backend && uv run pyright app/ tests/
```

Expected: `0 errors`.

- [ ] **Step 5: Run full backend tests**

Run:

```bash
cd backend && uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Confirm API type generation is not needed**

Run:

```bash
git diff --name-only
```

Expected: no files under:

```text
backend/app/models.py
backend/app/domains/garmin_analytics/api/
frontend/src/lib/api-types.ts
```

If those files changed unexpectedly, run:

```bash
bash scripts/generate-api-types.sh
cd frontend && npm run check
```

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/app/domains/garmin_analytics backend/app/infra/database.py backend/tests/architecture backend/tests/domains/garmin_analytics docs/superpowers/plans/2026-05-06-garmin-analytics-concern-layout.md
git commit -m "refactor: organize Garmin analytics by concern"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage:
  - Concern-based package structure: Tasks 2, 5, 6, 7, 8.
  - Domain/application boundary rules: Tasks 1 and 9.
  - Period-summary decomposition: Tasks 3 and 4.
  - Analysis versus insights split: Tasks 5, 6, 7, 8.
  - Test-first analytics rule: every production move task starts with characterization verification; period helper extraction starts with RED tests.
  - No API/schema changes: Task 9.
- Unresolved-marker scan:
  - No unresolved implementation markers.
  - Task 7 and Task 8 require preserving missing-date behavior from current code; this is explicit because the exact message/body must be copied from the current implementation during execution.
- Type consistency:
  - Public route-facing application facade function names remain unchanged through `application.insights` and existing API imports.
  - New domain helpers use existing Pydantic models and do not introduce new schemas.
