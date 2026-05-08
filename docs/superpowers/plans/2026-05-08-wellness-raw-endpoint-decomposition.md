# Wellness Raw Endpoint Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broad raw wellness API usage with metric-specific raw endpoints and remove `/api/wellness`.

**Architecture:** Keep the SQLite `wellness_data` mart and `BiometricReadRepository.load_wellness()` unchanged. Add narrow raw response contracts and metric-specific projection helpers in `garmin_analytics`, expose new `/raw` endpoints for each page, migrate every repo caller from the coarse `WellnessResponse`, then delete the broad route, contract, frontend helper, and broad flattener.

**Tech Stack:** FastAPI, Pydantic, SvelteKit, generated OpenAPI TypeScript types, pytest, ruff, pyright, `npm run check`, browser visual verification.

---

## Scope

This plan decomposes raw wellness API consumers only. It does not change ingest, parser behavior, daily aggregate calculations, period summaries, analysis endpoints, or insight endpoints.

This is an intentional API cleanup inside this repo. The final state has no `/api/wellness`, no `WellnessResponse`, no `api.getWellness()`, no `WellnessData`, and no `flatten_wellness()`.

## File Structure

- Modify `backend/app/domains/garmin_analytics/contracts.py`
  Add narrow raw response contracts and delete `WellnessResponse` after all callers migrate:
  - `HeartRateRawResponse`
  - `StressRawResponse`
  - `BodyBatteryRawResponse`
  - `SpO2RawResponse`
  - `RespirationRawResponse`

- Modify `backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py`
  Add metric-specific flatteners, then delete `flatten_wellness()`.

- Modify `backend/app/domains/garmin_analytics/application/raw_biometrics.py`
  Add metric-specific use cases, then delete `get_wellness()`:
  - `get_heart_rate_raw`
  - `get_stress_raw`
  - `get_body_battery_raw`
  - `get_spo2_raw`
  - `get_respiration_raw`

- Modify `backend/app/domains/garmin_analytics/routes.py`
  Add metric-specific route handlers and delete the broad wellness route:
  - `GET /api/heart-rate/raw`
  - `GET /api/stress/raw`
  - `GET /api/body-battery/raw`
  - `GET /api/pulse-ox/raw`
  - `GET /api/respiration/raw`

- Modify `backend/app/bootstrap/routing.py`
  Include the new respiration and pulse-ox raw routers if new router variables are introduced.

- Modify `backend/tests/domains/garmin_analytics/test_stats.py`
  Add tests for metric-specific raw flatteners and remove broad `flatten_wellness()` assertions.

- Modify `backend/tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py`
  Add use-case tests for new raw functions, including missing-date behavior.

- Modify `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`
  Guard that raw use cases remain in `raw_biometrics.py`, not in metric analysis/insight modules.

- Regenerate `frontend/src/lib/api-types.ts`
  Run `bash scripts/generate-api-types.sh` after backend route/contract changes.

- Modify `frontend/src/lib/api.ts`
  Add narrow raw API functions and types, then delete `WellnessData` and `getWellness()`.

- Modify frontend pages:
  - `frontend/src/routes/heart-rate/+page.svelte`
  - `frontend/src/routes/stress/+page.svelte`
  - `frontend/src/routes/body-battery/+page.svelte`
  - `frontend/src/routes/respiration/+page.svelte`
  - `frontend/src/routes/pulse-ox/+page.svelte`

- Update docs if route inventory changes:
  - `README.md`
  - `docs/ARCHITECTURE.md`

## Task 1: Add Narrow Raw Response Contracts

**Files:**
- Modify: `backend/app/domains/garmin_analytics/contracts.py`
- Test: `backend/tests/domains/garmin_analytics/test_stats.py`

- [ ] **Step 1: Write failing tests for narrow raw flatteners**

Append to `backend/tests/domains/garmin_analytics/test_stats.py`:

```python
from app.domains.garmin_analytics.domain.aggregates.biometric_responses import (
    flatten_body_battery,
    flatten_heart_rate,
    flatten_respiration,
    flatten_spo2,
    flatten_stress,
)


class TestFlattenWellnessMetricResponses:
    def test_heart_rate_response_contains_only_days_heart_rate_and_resting_hr(self):
        day = _make_day(date="2026-01-01", hr_values=[60, 70], resting_hr=48)

        resp = flatten_heart_rate([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.heart_rate] == [60, 70]
        assert resp.resting_hr[0].resting_hr == 48
        assert not hasattr(resp, "stress")

    def test_stress_response_contains_only_days_and_stress(self):
        day = _make_day(date="2026-01-01", stress_values=[20, 30])

        resp = flatten_stress([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.stress] == [20, 30]
        assert not hasattr(resp, "heart_rate")

    def test_body_battery_response_contains_only_days_and_body_battery(self):
        day = _make_day(date="2026-01-01", bb_values=[40, 80])

        resp = flatten_body_battery([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.body_battery] == [40, 80]

    def test_spo2_response_contains_only_days_and_spo2(self):
        day = _make_day(date="2026-01-01", spo2_values=[95, 96])

        resp = flatten_spo2([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.spo2] == [95, 96]

    def test_respiration_response_contains_only_days_and_respiration(self):
        day = _make_day(date="2026-01-01", resp_values=[12.0, 13.0])

        resp = flatten_respiration([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.respiration] == [12.0, 13.0]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py::TestFlattenWellnessMetricResponses -v
```

Expected: fail because the flatten helper imports do not exist.

- [ ] **Step 3: Add narrow contracts**

In `backend/app/domains/garmin_analytics/contracts.py`, place these near the existing raw reading response models. Do not add fields to `WellnessResponse`; it is removed after every repo caller migrates.

```python
class HeartRateRawResponse(DefaultsRequired):
    days: list[str]
    heart_rate: list[HeartRateReading]
    resting_hr: list[RestingHRReading]


class StressRawResponse(DefaultsRequired):
    days: list[str]
    stress: list[StressReading]


class BodyBatteryRawResponse(DefaultsRequired):
    days: list[str]
    body_battery: list[BodyBatteryReading]


class SpO2RawResponse(DefaultsRequired):
    days: list[str]
    spo2: list[SpO2Reading]


class RespirationRawResponse(DefaultsRequired):
    days: list[str]
    respiration: list[RespirationReading]
```

- [ ] **Step 4: Add metric-specific flatteners**

In `backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py`, import the new contracts and add:

```python
def flatten_heart_rate(days: list[DayWellness]) -> HeartRateRawResponse:
    return HeartRateRawResponse(
        days=[day.date for day in days],
        heart_rate=[reading for day in days for reading in day.heart_rate],
        resting_hr=[reading for day in days for reading in day.resting_hr],
    )


def flatten_stress(days: list[DayWellness]) -> StressRawResponse:
    return StressRawResponse(
        days=[day.date for day in days],
        stress=[reading for day in days for reading in day.stress],
    )


def flatten_body_battery(days: list[DayWellness]) -> BodyBatteryRawResponse:
    return BodyBatteryRawResponse(
        days=[day.date for day in days],
        body_battery=[reading for day in days for reading in day.body_battery],
    )


def flatten_spo2(days: list[DayWellness]) -> SpO2RawResponse:
    return SpO2RawResponse(
        days=[day.date for day in days],
        spo2=[reading for day in days for reading in day.spo2],
    )


def flatten_respiration(days: list[DayWellness]) -> RespirationRawResponse:
    return RespirationRawResponse(
        days=[day.date for day in days],
        respiration=[reading for day in days for reading in day.respiration],
    )
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_stats.py -v
```

Expected: pass.

## Task 2: Add Backend Raw Use Cases And Routes

**Files:**
- Modify: `backend/app/domains/garmin_analytics/application/raw_biometrics.py`
- Modify: `backend/app/domains/garmin_analytics/routes.py`
- Test: `backend/tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py`

- [ ] **Step 1: Write failing application tests**

Append to `backend/tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py`:

```python
from app.domains.garmin_analytics.application.raw_biometrics import (
    get_body_battery_raw,
    get_heart_rate_raw,
    get_respiration_raw,
    get_spo2_raw,
    get_stress_raw,
)
from app.domains.garmin_analytics.contracts import (
    BodyBatteryReading,
    DayWellness,
    HeartRateReading,
    RespirationReading,
    SpO2Reading,
    StressReading,
)


def test_raw_metric_use_cases_return_metric_specific_responses():
    repo = StubBiometricRepository(
        wellness=[
            DayWellness(
                date="2026-01-01",
                heart_rate=[HeartRateReading(timestamp="2026-01-01T01:00:00", value=60)],
                stress=[StressReading(timestamp="2026-01-01T01:00:00", value=20)],
                body_battery=[BodyBatteryReading(timestamp="2026-01-01T01:00:00", value=70)],
                spo2=[SpO2Reading(timestamp="2026-01-01T01:00:00", value=96, mode="sleep")],
                respiration=[RespirationReading(timestamp="2026-01-01T01:00:00", value=13.0)],
            )
        ]
    )

    assert get_heart_rate_raw(repo).heart_rate[0].value == 60
    assert get_stress_raw(repo).stress[0].value == 20
    assert get_body_battery_raw(repo).body_battery[0].value == 70
    assert get_spo2_raw(repo).spo2[0].value == 96
    assert get_respiration_raw(repo).respiration[0].value == 13.0


def test_raw_metric_use_cases_raise_lookup_error_for_missing_requested_date():
    repo = StubBiometricRepository(wellness=[])

    for load in [
        get_heart_rate_raw,
        get_stress_raw,
        get_body_battery_raw,
        get_spo2_raw,
        get_respiration_raw,
    ]:
        with pytest.raises(LookupError):
            load(repo, date="2026-01-01")
```

If this test file uses a different stub constructor, adapt only the setup to its existing local pattern. Keep the assertions and behavior unchanged.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py -v
```

Expected: fail because new use-case functions do not exist.

- [ ] **Step 3: Add use-case functions**

In `backend/app/domains/garmin_analytics/application/raw_biometrics.py`, import the new contracts and flatteners, then add:

```python
def get_heart_rate_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HeartRateRawResponse:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return flatten_heart_rate(days)


def get_stress_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> StressRawResponse:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return flatten_stress(days)


def get_body_battery_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> BodyBatteryRawResponse:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return flatten_body_battery(days)


def get_spo2_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> SpO2RawResponse:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return flatten_spo2(days)


def get_respiration_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> RespirationRawResponse:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return flatten_respiration(days)
```

- [ ] **Step 4: Add routes**

In `backend/app/domains/garmin_analytics/routes.py`, import the new response models and add:

```python
pulse_ox_router = APIRouter(prefix="/api/pulse-ox", tags=["pulse-ox"])
respiration_router = APIRouter(prefix="/api/respiration", tags=["respiration"])
```

Add route handlers:

```python
@heart_rate_router.get("/raw", response_model=HeartRateRawResponse)
def get_heart_rate_raw(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw heart-rate readings."""
    return raw_biometrics_uc.get_heart_rate_raw(
        build_container().garmin_biometrics_repo,
        date=date,
    )


@stress_router.get("/raw", response_model=StressRawResponse)
def get_stress_raw(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw stress readings."""
    return raw_biometrics_uc.get_stress_raw(
        build_container().garmin_biometrics_repo,
        date=date,
    )


@body_battery_router.get("/raw", response_model=BodyBatteryRawResponse)
def get_body_battery_raw(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw body-battery readings."""
    return raw_biometrics_uc.get_body_battery_raw(
        build_container().garmin_biometrics_repo,
        date=date,
    )


@pulse_ox_router.get("/raw", response_model=SpO2RawResponse)
def get_pulse_ox_raw(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw pulse-ox readings."""
    return raw_biometrics_uc.get_spo2_raw(
        build_container().garmin_biometrics_repo,
        date=date,
    )


@respiration_router.get("/raw", response_model=RespirationRawResponse)
def get_respiration_raw(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw respiration readings."""
    return raw_biometrics_uc.get_respiration_raw(
        build_container().garmin_biometrics_repo,
        date=date,
    )
```

- [ ] **Step 5: Register new routers**

In `backend/app/bootstrap/routing.py`, import and include `pulse_ox_router` and `respiration_router` if they are new variables.

```python
from app.domains.garmin_analytics.routes import (
    body_battery_router,
    daily_aggregates_router,
    dashboard_router,
    heart_rate_router,
    hrv_router,
    pulse_ox_router,
    respiration_router,
    skin_temp_router,
    sleep_router,
    stress_router,
    wellness_router,
)
```

Add:

```python
app.include_router(respiration_router)
app.include_router(pulse_ox_router)
```

- [ ] **Step 6: Run backend focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_garmin_analytics_biometrics_application.py tests/architecture/test_architecture_garmin_analytics_boundaries.py -v
```

Expected: pass.

## Task 3: Regenerate API Types

**Files:**
- Modify: `frontend/src/lib/api-types.ts`

- [ ] **Step 1: Regenerate TypeScript API contracts**

Run:

```bash
bash scripts/generate-api-types.sh
```

Expected: `frontend/src/lib/api-types.ts` changes and includes the new raw response schemas and `/api/*/raw` paths.

- [ ] **Step 2: Inspect generated diff**

Run:

```bash
git diff -- frontend/src/lib/api-types.ts
```

Expected: generated OpenAPI type changes only. Do not hand-edit this file.

## Task 4: Add Frontend API Helpers

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add narrow raw types**

Add near existing type exports:

```ts
export type HeartRateRawData = Schemas['HeartRateRawResponse'];
export type StressRawData = Schemas['StressRawResponse'];
export type BodyBatteryRawData = Schemas['BodyBatteryRawResponse'];
export type SpO2RawData = Schemas['SpO2RawResponse'];
export type RespirationRawData = Schemas['RespirationRawResponse'];
```

- [ ] **Step 2: Add narrow API methods**

Add to the `api` object:

```ts
getHeartRateRaw: (date?: string) =>
    fetchJson<HeartRateRawData>(`/api/heart-rate/raw${date ? `?date=${date}` : ''}`),
getStressRaw: (date?: string) =>
    fetchJson<StressRawData>(`/api/stress/raw${date ? `?date=${date}` : ''}`),
getBodyBatteryRaw: (date?: string) =>
    fetchJson<BodyBatteryRawData>(`/api/body-battery/raw${date ? `?date=${date}` : ''}`),
getPulseOxRaw: (date?: string) =>
    fetchJson<SpO2RawData>(`/api/pulse-ox/raw${date ? `?date=${date}` : ''}`),
getRespirationRaw: (date?: string) =>
    fetchJson<RespirationRawData>(`/api/respiration/raw${date ? `?date=${date}` : ''}`),
```

- [ ] **Step 3: Run frontend type check**

Run:

```bash
cd frontend && npm run check
```

Expected: pass.

## Task 5: Migrate Frontend Pages To Narrow Raw Endpoints

**Files:**
- Modify: `frontend/src/routes/heart-rate/+page.svelte`
- Modify: `frontend/src/routes/stress/+page.svelte`
- Modify: `frontend/src/routes/body-battery/+page.svelte`
- Modify: `frontend/src/routes/respiration/+page.svelte`
- Modify: `frontend/src/routes/pulse-ox/+page.svelte`

- [ ] **Step 1: Migrate heart-rate page**

In `frontend/src/routes/heart-rate/+page.svelte`:

```ts
import { api, type DailyAggregates, type HeartRateRawData } from '$lib/api';
```

Replace `WellnessData` state types with `HeartRateRawData`:

```ts
let latestIntraday: HeartRateRawData | null = $state(null);
let historicalIntraday: HeartRateRawData | null = $state(null);
```

Replace API calls:

```ts
api.getHeartRateRaw(latest)
api.getHeartRateRaw(date)
```

Update `buildIntradayConfig` signature:

```ts
function buildIntradayConfig(
    intraday: HeartRateRawData,
    resting: number | null | undefined
): ChartConfiguration<'line'> {
```

- [ ] **Step 2: Migrate stress page**

In `frontend/src/routes/stress/+page.svelte`:

```ts
import { api, type DailyAggregates, type StressRawData } from '$lib/api';
```

Replace:

```ts
let intradayData: StressRawData | null = $state(null);
const onDateChange = createDateLoader<StressRawData>({
    clearData: () => { intradayData = null; },
    fetchByDate: (date) => api.getStressRaw(date),
    setData: (data) => { intradayData = data; },
});
```

Replace initial load call:

```ts
const data = await api.getStressRaw(selectedDate);
```

- [ ] **Step 3: Migrate body-battery page**

In `frontend/src/routes/body-battery/+page.svelte`:

```ts
import { api, type BodyBatteryRawData, type DailyAggregates } from '$lib/api';
```

Use:

```ts
let intradayData: BodyBatteryRawData | null = $state(null);
fetchByDate: (date) => api.getBodyBatteryRaw(date),
const data = await api.getBodyBatteryRaw(selectedDate);
```

- [ ] **Step 4: Migrate respiration page**

In `frontend/src/routes/respiration/+page.svelte`:

```ts
import { api, type DailyAggregates, type RespirationRawData } from '$lib/api';
```

Use:

```ts
let intradayData: RespirationRawData | null = $state(null);
fetchByDate: (date) => api.getRespirationRaw(date),
const data = await api.getRespirationRaw(date);
```

- [ ] **Step 5: Migrate pulse-ox page**

In `frontend/src/routes/pulse-ox/+page.svelte`:

```ts
import { api, type DailyAggregates, type SpO2RawData } from '$lib/api';
```

Use:

```ts
let intradayData: SpO2RawData | null = $state(null);
fetchByDate: (date) => api.getPulseOxRaw(date),
const data = await api.getPulseOxRaw(date);
```

- [ ] **Step 6: Verify no page depends on `getWellness()`**

Run:

```bash
rg -n "getWellness\\(|WellnessData" frontend/src
```

Expected: no matches. If `frontend/src/lib/api.ts` still defines either symbol, delete them before continuing.

- [ ] **Step 7: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected: pass.

## Task 6: Delete Broad Wellness API Surface

**Files:**
- Modify: `backend/app/domains/garmin_analytics/contracts.py`
- Modify: `backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py`
- Modify: `backend/app/domains/garmin_analytics/application/raw_biometrics.py`
- Modify: `backend/app/domains/garmin_analytics/routes.py`
- Modify: `backend/app/bootstrap/routing.py`
- Modify: `backend/tests/domains/garmin_analytics/test_stats.py`
- Modify: `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`
- Modify: `frontend/src/lib/api.ts`
- Regenerate: `frontend/src/lib/api-types.ts`

- [ ] **Step 1: Confirm there are no remaining runtime callers**

Run:

```bash
rg -n "getWellness\\(|/api/wellness|WellnessResponse|WellnessData|flatten_wellness|get_wellness" backend/app frontend/src README.md docs/ARCHITECTURE.md
```

Expected before deletion: matches only in the broad backend route/use case/contract/helper, generated API types, `frontend/src/lib/api.ts`, and docs that are updated in Task 7. If any page, component, analysis module, or other runtime caller appears, migrate it to a metric-specific raw endpoint first.

- [ ] **Step 2: Delete the frontend broad helper**

In `frontend/src/lib/api.ts`, remove:

```ts
export type WellnessData = Schemas['WellnessResponse'];
```

Remove the API method:

```ts
getWellness: (date?: string) =>
    fetchJson<WellnessData>(`/api/wellness${date ? `?date=${date}` : ''}`),
```

- [ ] **Step 3: Delete the broad backend route**

In `backend/app/domains/garmin_analytics/routes.py`, remove:

- the `WellnessResponse` import
- the broad `wellness_router = APIRouter(...)`
- the `get_wellness_route(...)` handler
- the `get_wellness(...)` use-case import if it is now unused

In `backend/app/bootstrap/routing.py`, remove:

- the `wellness_router` import
- `app.include_router(wellness_router)`

- [ ] **Step 4: Delete the broad use case, helper, and contract**

In `backend/app/domains/garmin_analytics/application/raw_biometrics.py`, remove:

- `get_wellness(...)`
- any import used only by that function

In `backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py`, remove:

- `flatten_wellness(...)`
- any import used only by that function

In `backend/app/domains/garmin_analytics/contracts.py`, remove:

- `WellnessResponse`

- [ ] **Step 5: Update tests to enforce deletion**

In `backend/tests/domains/garmin_analytics/test_stats.py`, delete the broad `flatten_wellness()` tests and imports. Keep the metric-specific raw flattener tests from Task 1.

In `backend/tests/architecture/test_architecture_garmin_analytics_boundaries.py`, add an assertion that the broad raw endpoint and contract are gone:

```python
def test_broad_wellness_raw_endpoint_has_been_removed():
    routes = read_repo_file("backend/app/domains/garmin_analytics/routes.py")
    contracts = read_repo_file("backend/app/domains/garmin_analytics/contracts.py")
    raw_biometrics = read_repo_file(
        "backend/app/domains/garmin_analytics/application/raw_biometrics.py"
    )
    responses = read_repo_file(
        "backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py"
    )

    assert 'prefix="/api/wellness"' not in routes
    assert "def get_wellness" not in routes
    assert "def get_wellness" not in raw_biometrics
    assert "class WellnessResponse" not in contracts
    assert "def flatten_wellness" not in responses
```

Adjust helper names to match the existing architecture test utilities.

- [ ] **Step 6: Regenerate API types**

Run:

```bash
bash scripts/generate-api-types.sh
```

Expected: `frontend/src/lib/api-types.ts` no longer contains `WellnessResponse`.

- [ ] **Step 7: Verify broad wellness API surface is absent**

Run:

```bash
rg -n "getWellness\\(|/api/wellness|WellnessResponse|WellnessData|flatten_wellness|get_wellness" backend/app frontend/src
```

Expected: no matches.

## Task 7: Docs And Visual Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Update route documentation**

In `README.md`, update the API/route section to mention the new raw metric endpoints:

```md
- Raw metric readings:
  `/api/heart-rate/raw`, `/api/stress/raw`, `/api/body-battery/raw`,
  `/api/respiration/raw`, `/api/pulse-ox/raw`
```

In `docs/ARCHITECTURE.md`, update the Garmin Analytics Boundary section:

```md
- Raw biometric views use metric-specific `/api/*/raw` endpoints so each page
  receives only the readings it renders.
```

- [ ] **Step 2: Verify docs do not reference the deleted broad endpoint**

Run:

```bash
rg -n "/api/wellness|WellnessResponse|WellnessData|getWellness" README.md docs/ARCHITECTURE.md
```

Expected: no matches.

- [ ] **Step 3: Run backend validation**

Run:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Run frontend validation**

Run:

```bash
cd frontend && npm run check
```

Expected: pass.

- [ ] **Step 5: Start local servers**

Run backend:

```bash
cd backend && uv run uvicorn app.main:app --reload
```

Run frontend:

```bash
cd frontend && npm run dev
```

- [ ] **Step 6: Visually verify modified pages**

Using browser MCP tools, open and screenshot:

- `http://localhost:5173/heart-rate`
- `http://localhost:5173/stress`
- `http://localhost:5173/body-battery`
- `http://localhost:5173/respiration`
- `http://localhost:5173/pulse-ox`

For each page verify:

- The intraday chart renders.
- The reading count renders.
- Changing the selected date reloads the intraday data.
- No browser console/API errors are visible.
- No chart or text overlap was introduced.

## Final Verification

Run all required checks after completing all tasks:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
cd frontend && npm run check
git diff --check
```

Expected:

- Ruff: `All checks passed!`
- Pyright: `0 errors`
- Pytest: all tests pass
- Frontend check: no Svelte/TypeScript errors
- `git diff --check`: no whitespace errors

## Self-Review Checklist

- The broad raw wellness endpoint is removed.
- `WellnessResponse`, `WellnessData`, `api.getWellness()`, `flatten_wellness()`, and `get_wellness()` are absent from backend app code, frontend source, README, and architecture docs.
- New raw endpoints return only the body parameter needed by each frontend page.
- API types were regenerated, not hand-edited.
- Backend validation, frontend validation, and browser visual verification are complete.
