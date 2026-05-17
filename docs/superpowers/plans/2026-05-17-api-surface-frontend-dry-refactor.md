# API Surface And Frontend DRY Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed, metric-scoped API contracts that let the frontend stop loading the full daily aggregate payload on every metric page, then migrate the frontend API client and metric pages without changing user-visible behavior.

**Architecture:** Keep `/api/daily-aggregates` as the full daily metric mart endpoint, but replace ambiguous base raw routes with canonical `/raw` routes. Add narrow Garmin analytics read endpoints beside the current metric routes, backed by the existing daily metric mart and period summary computation. Then move the frontend to generated OpenAPI path typing and metric-specific page data contracts before extracting shared page helpers.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, pytest, uv, Svelte 5, TypeScript, openapi-typescript, openapi-fetch, SvelteKit.

---

## Scope

This plan covers four decisions:

- Automate frontend endpoint/query/body typing with OpenAPI-generated `paths`.
- Canonicalize raw metric paths by replacing ambiguous base routes with `/raw` routes for sleep, HRV, and skin temperature.
- Remove the misleading `1M` frontend trend option because backend period summaries currently start at `3M`.
- Add metric-scoped daily endpoints so metric pages do not load the whole `/api/daily-aggregates` response.

This plan intentionally does not redesign metric detail pages visually or merge all metric routes behind a generic `/api/metrics/{metric}` endpoint. The only route removals are the ambiguous base raw routes `/api/sleep`, `/api/hrv`, and `/api/skin-temp`.

## File Map

- `backend/app/domains/garmin_analytics/contracts/period.py`
  Owns daily-summary response contracts for metric-scoped daily endpoints.

- `backend/app/domains/garmin_analytics/application/daily_aggregates.py`
  Owns loading persisted daily metrics and slicing the existing period-window summaries by metric.

- `backend/app/domains/garmin_analytics/routes.py`
  Owns the new metric daily routes and canonical raw routes.

- `backend/tests/domains/garmin_analytics/test_metric_daily_routes.py`
  New route/use-case tests proving metric-scoped daily endpoints match the corresponding subset of `/api/daily-aggregates`.

- `backend/tests/domains/garmin_analytics/test_raw_routes.py`
  New route tests proving `/api/sleep/raw`, `/api/hrv/raw`, and `/api/skin-temp/raw` exist and the old ambiguous base raw routes are removed.

- `frontend/package.json`, `frontend/package-lock.json`
  Add `openapi-fetch`.

- `frontend/src/lib/api.ts`
  Switch semantic wrapper methods to generated OpenAPI path typing, and rename sleep/HRV/skin-temperature raw methods to match canonical `/raw` routes.

- `frontend/src/lib/trend-range.ts`
  Remove `1M` and the non-identity `PERIOD_KEY_MAP` mapping.

- `frontend/src/routes/*/+page.svelte`
  Migrate metric pages to metric daily endpoints and use canonical `/raw` methods.

- `README.md`, `docs/ARCHITECTURE.md`
  Update route inventory and frontend API convention notes.

---

## Task 1: Add Backend Tests For Metric-Scoped Daily Endpoints

**Files:**
- Create: `backend/tests/domains/garmin_analytics/test_metric_daily_routes.py`

- [ ] **Step 1: Write failing route tests**

Create `backend/tests/domains/garmin_analytics/test_metric_daily_routes.py` with this content:

```python
"""Route coverage for metric-scoped daily Garmin analytics endpoints."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _get(path: str) -> dict:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_heart_rate_daily_matches_daily_aggregates_subset() -> None:
    full = _get("/api/daily-aggregates")
    scoped = _get("/api/heart-rate/daily")

    assert scoped["days"] == full["days"]
    assert scoped["daily"] == [
        {
            "date": row["date"],
            "utc_offset_hours": row["utc_offset_hours"],
            "heart_rate": row["heart_rate"],
        }
        for row in full["daily"]
    ]
    assert scoped["period_windows"] == {
        label: summary["heart_rate"]
        for label, summary in full["period_windows"].items()
    }


def test_hrv_daily_matches_daily_aggregates_subset() -> None:
    full = _get("/api/daily-aggregates")
    scoped = _get("/api/hrv/daily")

    assert scoped["days"] == full["days"]
    assert scoped["daily"] == [
        {
            "date": row["date"],
            "utc_offset_hours": row["utc_offset_hours"],
            "hrv": row["hrv"],
        }
        for row in full["daily"]
    ]
    assert scoped["period_windows"] == {
        label: summary["hrv"]
        for label, summary in full["period_windows"].items()
    }


def test_sleep_daily_matches_daily_aggregates_subset() -> None:
    full = _get("/api/daily-aggregates")
    scoped = _get("/api/sleep/daily")

    assert scoped["days"] == full["days"]
    assert scoped["daily"] == [
        {
            "date": row["date"],
            "utc_offset_hours": row["utc_offset_hours"],
            "sleep": row["sleep"],
        }
        for row in full["daily"]
    ]
    assert scoped["period_windows"] == {
        label: summary["sleep"]
        for label, summary in full["period_windows"].items()
    }


def test_scalar_metric_daily_endpoints_match_daily_aggregates_subsets() -> None:
    full = _get("/api/daily-aggregates")
    cases = [
        ("/api/stress/daily", "stress"),
        ("/api/respiration/daily", "respiration"),
        ("/api/pulse-ox/daily", "spo2"),
        ("/api/skin-temp/daily", "skin_temp"),
        ("/api/body-battery/daily", "body_battery"),
    ]

    for path, field in cases:
        scoped = _get(path)
        assert scoped["days"] == full["days"]
        assert scoped["daily"] == [
            {
                "date": row["date"],
                "utc_offset_hours": row["utc_offset_hours"],
                field: row[field],
            }
            for row in full["daily"]
        ]
        assert scoped["period_windows"] == {
            label: summary[field]
            for label, summary in full["period_windows"].items()
        }
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_metric_daily_routes.py -v
```

Expected result: tests fail with `404 Not Found` for the new `/daily` endpoints.

---

## Task 2: Implement Metric-Scoped Daily Backend Contracts And Routes

**Files:**
- Modify: `backend/app/domains/garmin_analytics/contracts/period.py`
- Modify: `backend/app/domains/garmin_analytics/contracts/__init__.py`
- Modify: `backend/app/domains/garmin_analytics/application/daily_aggregates.py`
- Modify: `backend/app/domains/garmin_analytics/routes.py`
- Test: `backend/tests/domains/garmin_analytics/test_metric_daily_routes.py`

- [ ] **Step 1: Add metric daily contracts**

In `backend/app/domains/garmin_analytics/contracts/period.py`, add these imports:

```python
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    HRZoneBucket,
)
```

Keep the existing `DailyMetric` and `HRZoneBucket` imports represented once. Then add these classes below `DailyAggregatesResponse`:

```python
class HeartRateDailyPoint(DefaultsRequired):
    """Heart-rate daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    heart_rate: DailyHeartRateStats


class HeartRateDailyResponse(DefaultsRequired):
    """Daily heart-rate metrics plus heart-rate period summaries."""

    days: list[str]
    daily: list[HeartRateDailyPoint]
    period_windows: dict[str, PeriodHeartRateStats] = {}


class HrvDailyPoint(DefaultsRequired):
    """HRV daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    hrv: DailyHrvStats


class HrvDailyResponse(DefaultsRequired):
    """Daily HRV metrics plus HRV period summaries."""

    days: list[str]
    daily: list[HrvDailyPoint]
    period_windows: dict[str, PeriodHrvStats] = {}


class SleepDailyPoint(DefaultsRequired):
    """Sleep daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    sleep: DailySleepStats


class SleepDailyResponse(DefaultsRequired):
    """Daily sleep metrics plus sleep period summaries."""

    days: list[str]
    daily: list[SleepDailyPoint]
    period_windows: dict[str, PeriodSleepStats] = {}


class StressDailyPoint(DefaultsRequired):
    """Stress daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    stress: DailyMetricStats


class StressDailyResponse(DefaultsRequired):
    """Daily stress metrics plus stress period summaries."""

    days: list[str]
    daily: list[StressDailyPoint]
    period_windows: dict[str, PeriodMetricStats] = {}


class RespirationDailyPoint(DefaultsRequired):
    """Respiration daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    respiration: DailyMetricStats


class RespirationDailyResponse(DefaultsRequired):
    """Daily respiration metrics plus respiration period summaries."""

    days: list[str]
    daily: list[RespirationDailyPoint]
    period_windows: dict[str, PeriodMetricStats] = {}


class SpO2DailyPoint(DefaultsRequired):
    """Pulse-ox daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    spo2: DailyMetricStats


class SpO2DailyResponse(DefaultsRequired):
    """Daily pulse-ox metrics plus pulse-ox period summaries."""

    days: list[str]
    daily: list[SpO2DailyPoint]
    period_windows: dict[str, PeriodSpo2Stats] = {}


class SkinTempDailyPoint(DefaultsRequired):
    """Skin-temperature daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    skin_temp: DailySkinTempStats


class SkinTempDailyResponse(DefaultsRequired):
    """Daily skin-temperature metrics plus skin-temperature period summaries."""

    days: list[str]
    daily: list[SkinTempDailyPoint]
    period_windows: dict[str, PeriodSkinTempStats] = {}


class BodyBatteryDailyPoint(DefaultsRequired):
    """Body Battery daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    body_battery: DailyBodyBatteryStats


class BodyBatteryDailyResponse(DefaultsRequired):
    """Daily Body Battery metrics plus Body Battery period summaries."""

    days: list[str]
    daily: list[BodyBatteryDailyPoint]
    period_windows: dict[str, PeriodBodyBatteryStats] = {}
```

- [ ] **Step 2: Re-export new contracts**

In `backend/app/domains/garmin_analytics/contracts/__init__.py`, import and export all new `*DailyPoint` and `*DailyResponse` classes from `.period`.

- [ ] **Step 3: Add use-case helpers**

In `backend/app/domains/garmin_analytics/application/daily_aggregates.py`, import the new contracts and add:

```python
def _days(metrics: list[DailyMetric]) -> list[str]:
    return [metric.date for metric in metrics]


def _window_field(
    repo: BiometricReadRepository,
    field: str,
) -> dict[str, object]:
    return {
        label: getattr(summary, field)
        for label, summary in load_windowed_period_summary(repo).items()
    }
```

Then add one use case per endpoint:

```python
def get_heart_rate_daily(repo: BiometricReadRepository) -> HeartRateDailyResponse:
    metrics = repo.load_daily_metrics()
    return HeartRateDailyResponse(
        days=_days(metrics),
        daily=[
            HeartRateDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                heart_rate=metric.heart_rate,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, "heart_rate"),
    )
```

Repeat the same pattern for:

- `get_hrv_daily()` using `HrvDailyResponse`, `HrvDailyPoint`, and `"hrv"`.
- `get_sleep_daily()` using `SleepDailyResponse`, `SleepDailyPoint`, and `"sleep"`.
- `get_stress_daily()` using `StressDailyResponse`, `StressDailyPoint`, and `"stress"`.
- `get_respiration_daily()` using `RespirationDailyResponse`, `RespirationDailyPoint`, and `"respiration"`.
- `get_spo2_daily()` using `SpO2DailyResponse`, `SpO2DailyPoint`, and `"spo2"`.
- `get_skin_temp_daily()` using `SkinTempDailyResponse`, `SkinTempDailyPoint`, and `"skin_temp"`.
- `get_body_battery_daily()` using `BodyBatteryDailyResponse`, `BodyBatteryDailyPoint`, and `"body_battery"`.

After adding these helpers, run pyright once. If pyright rejects `_window_field()` returning `dict[str, object]` for typed response fields, replace `_window_field()` with typed helper functions per period-summary type instead of using casts.

- [ ] **Step 4: Add routes**

In `backend/app/domains/garmin_analytics/routes.py`, import the new response contracts and add these route handlers next to each metric router:

```python
@heart_rate_router.get("/daily", response_model=HeartRateDailyResponse)
def get_heart_rate_daily(repo: BiometricsRepo):
    """Return daily heart-rate metrics and period summaries."""
    return daily_aggregates_uc.get_heart_rate_daily(repo)
```

Add equivalent `/daily` handlers for HRV, sleep, stress, body battery, respiration, pulse ox, and skin temperature.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_metric_daily_routes.py -v
```

Expected result: all tests pass.

---

## Task 3: Replace Ambiguous Base Raw Routes With Canonical `/raw` Routes

**Files:**
- Create: `backend/tests/domains/garmin_analytics/test_raw_routes.py`
- Modify: `backend/app/domains/garmin_analytics/routes.py`

- [ ] **Step 1: Write failing raw route tests**

Create `backend/tests/domains/garmin_analytics/test_raw_routes.py`:

```python
"""Route coverage for canonical Garmin raw metric endpoints."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _status(path: str) -> int:
    response = client.get(path)
    return response.status_code


def test_sleep_raw_route_replaces_ambiguous_base_route() -> None:
    assert _status("/api/sleep/raw") == 200
    assert _status("/api/sleep") == 404
    assert _status("/api/sleep/analysis") == 200


def test_hrv_raw_route_replaces_ambiguous_base_route() -> None:
    assert _status("/api/hrv/raw") == 200
    assert _status("/api/hrv") == 404
    assert _status("/api/hrv/analysis") == 200
    assert _status("/api/hrv/insights") == 200


def test_skin_temp_raw_route_replaces_ambiguous_base_route() -> None:
    assert _status("/api/skin-temp/raw") == 200
    assert _status("/api/skin-temp") == 404
```

- [ ] **Step 2: Run the failing raw route tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_raw_routes.py -v
```

Expected result: tests fail because `/raw` routes do not exist yet and the old base routes still return `200`.

- [ ] **Step 3: Move base raw routes to `/raw`**

In `backend/app/domains/garmin_analytics/routes.py`, change the sleep base raw route from:

```python
@sleep_router.get("", response_model=SleepResponse)
def get_sleep(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get sleep data (stages, assessment scores)."""
    return raw_biometrics_uc.get_sleep(repo, date=date)
```

to:

```python
@sleep_router.get("/raw", response_model=SleepResponse)
def get_sleep_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw sleep data (stages, assessment scores)."""
    return raw_biometrics_uc.get_sleep(repo, date=date)
```

Change the HRV base raw route from:

```python
@hrv_router.get("", response_model=HrvResponse)
def get_hrv(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get HRV data (values, summaries)."""
    return raw_biometrics_uc.get_hrv(repo, date=date)
```

to:

```python
@hrv_router.get("/raw", response_model=HrvResponse)
def get_hrv_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw HRV data (values, summaries)."""
    return raw_biometrics_uc.get_hrv(repo, date=date)
```

Change the skin-temperature base raw route from:

```python
@skin_temp_router.get("", response_model=SkinTempResponse)
def get_skin_temp(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get skin temperature data."""
    return raw_biometrics_uc.get_skin_temp(repo, date=date)
```

to:

```python
@skin_temp_router.get("/raw", response_model=SkinTempResponse)
def get_skin_temp_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw skin-temperature data."""
    return raw_biometrics_uc.get_skin_temp(repo, date=date)
```

- [ ] **Step 4: Run raw route tests**

Run:

```bash
cd backend && uv run pytest tests/domains/garmin_analytics/test_raw_routes.py -v
```

Expected result: all tests pass.

---

## Task 4: Regenerate API Types And Install Typed Fetch Client

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/lib/api-types.ts`
- Modify: `frontend/openapi.json`

- [ ] **Step 1: Install `openapi-fetch`**

Run:

```bash
cd frontend && npm install openapi-fetch
```

Expected result: `frontend/package.json` includes `openapi-fetch` under dependencies and `frontend/package-lock.json` is updated.

- [ ] **Step 2: Regenerate OpenAPI types**

Run:

```bash
bash scripts/generate-api-types.sh
```

Expected result: `frontend/openapi.json` and `frontend/src/lib/api-types.ts` include the new `/daily` and `/raw` paths, and no longer include `/api/sleep`, `/api/hrv`, or `/api/skin-temp` base raw operations.

- [ ] **Step 3: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected result: check passes before the API wrapper migration begins.

---

## Task 5: Move `frontend/src/lib/api.ts` To Generated Path Typing

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Import generated `paths` and `openapi-fetch`**

Change the top of `frontend/src/lib/api.ts` to:

```ts
import createClient from 'openapi-fetch';
import type { components, paths } from './api-types';
import { API_BASE } from './config';
```

Add:

```ts
const client = createClient<paths>({ baseUrl: API_BASE });
```

- [ ] **Step 2: Add response helpers**

Replace `fetchJson()` and `sendJson()` with:

```ts
function unwrap<T>(data: T | undefined, error: unknown): T {
	if (error) {
		throw new Error(typeof error === 'string' ? error : JSON.stringify(error));
	}
	if (data === undefined) {
		throw new Error('API response did not include JSON data');
	}
	return data;
}
```

- [ ] **Step 3: Migrate read methods**

Rewrite methods to use typed paths. Examples:

```ts
getDailyAggregates: async () => {
	const { data, error } = await client.GET('/api/daily-aggregates');
	return unwrap(data, error);
},
getHeartRateRaw: async (date?: string) => {
	const { data, error } = await client.GET('/api/heart-rate/raw', {
		params: { query: date ? { date } : {} }
	});
	return unwrap(data, error);
},
getSleepRaw: async (date?: string) => {
	const { data, error } = await client.GET('/api/sleep/raw', {
		params: { query: date ? { date } : {} }
	});
	return unwrap(data, error);
},
getHrvRaw: async (date?: string) => {
	const { data, error } = await client.GET('/api/hrv/raw', {
		params: { query: date ? { date } : {} }
	});
	return unwrap(data, error);
},
getSkinTempRaw: async (date?: string) => {
	const { data, error } = await client.GET('/api/skin-temp/raw', {
		params: { query: date ? { date } : {} }
	});
	return unwrap(data, error);
},
getToday: async (date: string) => {
	const { data, error } = await client.GET('/api/today', {
		params: { query: { date } }
	});
	return unwrap(data, error);
}
```

Add new semantic methods:

```ts
getHeartRateDaily: async () => {
	const { data, error } = await client.GET('/api/heart-rate/daily');
	return unwrap(data, error);
},
getHrvDaily: async () => {
	const { data, error } = await client.GET('/api/hrv/daily');
	return unwrap(data, error);
},
getSleepDaily: async () => {
	const { data, error } = await client.GET('/api/sleep/daily');
	return unwrap(data, error);
},
getStressDaily: async () => {
	const { data, error } = await client.GET('/api/stress/daily');
	return unwrap(data, error);
},
getBodyBatteryDaily: async () => {
	const { data, error } = await client.GET('/api/body-battery/daily');
	return unwrap(data, error);
},
getRespirationDaily: async () => {
	const { data, error } = await client.GET('/api/respiration/daily');
	return unwrap(data, error);
},
getPulseOxDaily: async () => {
	const { data, error } = await client.GET('/api/pulse-ox/daily');
	return unwrap(data, error);
},
getSkinTempDaily: async () => {
	const { data, error } = await client.GET('/api/skin-temp/daily');
	return unwrap(data, error);
}
```

- [ ] **Step 4: Migrate write methods**

Rewrite write methods with typed bodies. Example:

```ts
updateTodayCard: async (date: string, occurrenceKey: string, payload: TodayCardLogUpdate) => {
	const { data, error } = await client.PUT('/api/today/{date}/cards/{occurrence_key}', {
		params: { path: { date, occurrence_key: occurrenceKey } },
		body: payload
	});
	return unwrap(data, error);
}
```

Use equivalent `client.POST` or `client.PUT` calls for profile, check-ins, notes, experiments, artifacts, programs, and assistant thread creation.

- [ ] **Step 5: Keep streaming code separate**

Do not change:

- `frontend/src/lib/sse.ts`
- `frontend/src/lib/assistant-stream.ts`

These use `EventSource` and streaming `fetch`, so the typed JSON client does not apply cleanly.

- [ ] **Step 6: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected result: all TypeScript and Svelte checks pass.

---

## Task 6: Remove The Misleading `1M` Trend Range

**Files:**
- Modify: `frontend/src/lib/trend-range.ts`
- Modify: metric pages importing `PERIOD_KEY_MAP`

- [ ] **Step 1: Simplify trend ranges**

Change `frontend/src/lib/trend-range.ts` to:

```ts
import { localDateIso } from './date';

/** Shared trend-range utilities for time-window filtering across all tabs. */

export type TrendRange = '3M' | '6M' | 'All';
export const TREND_RANGES: TrendRange[] = ['3M', '6M', 'All'];

/** Returns an ISO date string cutoff for the given range, or null for 'All'. */
export function trendCutoff(range: TrendRange): string | null {
	if (range === 'All') return null;
	const d = new Date();
	const months = range === '3M' ? 3 : 6;
	d.setMonth(d.getMonth() - months);
	return localDateIso(d);
}

/** Filter items with a `date` field by the given trend range. */
export function filterByRange<T extends { date: string }>(items: T[], range: TrendRange): T[] {
	const cutoff = trendCutoff(range);
	if (!cutoff) return items;
	return items.filter((item) => item.date >= cutoff);
}
```

- [ ] **Step 2: Replace `PERIOD_KEY_MAP` use**

In metric pages, replace:

```ts
agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]]
```

with:

```ts
daily?.period_windows?.[trendRange]
```

Use the page's new metric daily state variable after Task 7. If doing this task before Task 7, replace only imports and places where the current data object still has `period_windows`.

- [ ] **Step 3: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected result: pages compile with `3M`, `6M`, and `All` only.

---

## Task 7: Migrate Metric Pages To Metric-Scoped Daily Endpoints

**Files:**
- Modify: `frontend/src/routes/heart-rate/+page.svelte`
- Modify: `frontend/src/routes/hrv/+page.svelte`
- Modify: `frontend/src/routes/sleep/+page.svelte`
- Modify: `frontend/src/routes/stress/+page.svelte`
- Modify: `frontend/src/routes/body-battery/+page.svelte`
- Modify: `frontend/src/routes/respiration/+page.svelte`
- Modify: `frontend/src/routes/pulse-ox/+page.svelte`
- Modify: `frontend/src/routes/skin-temp/+page.svelte`

- [ ] **Step 1: Start with simpler metric pages**

For `frontend/src/routes/stress/+page.svelte`, replace:

```ts
type DailyAggregates
```

with:

```ts
type StressDailyResponse
```

Rename state:

```ts
let daily: StressDailyResponse | null = $state(null);
```

Change the loader:

```ts
const [nextDaily, nextAnalysis] = await Promise.all([
	api.getStressDaily(),
	api.getStressAnalysis()
]);
daily = nextDaily;
analysis = nextAnalysis;
```

Change date selector and stats reads:

```svelte
<DateSelector days={daily.days} selected={selectedDate} onchange={onDateChange} />
```

```ts
const pw = daily?.period_windows?.[trendRange];
```

Update the template guard from `{:else if agg}` to `{:else if daily}`.

- [ ] **Step 2: Repeat the same migration for body battery**

Use:

```ts
type BodyBatteryDailyResponse
api.getBodyBatteryDaily()
daily.period_windows?.[trendRange]
daily.days
```

- [ ] **Step 3: Repeat the same migration for respiration**

Use:

```ts
type RespirationDailyResponse
api.getRespirationDaily()
daily.period_windows?.[trendRange]
daily.days
daily.daily.map((d) => d.respiration)
```

- [ ] **Step 4: Repeat the same migration for pulse ox**

Use:

```ts
type SpO2DailyResponse
api.getPulseOxDaily()
daily.period_windows?.[trendRange]
daily.days
daily.daily.map((d) => d.spo2)
```

- [ ] **Step 5: Repeat the same migration for sleep**

Use:

```ts
type SleepDailyResponse
api.getSleepDaily()
api.getSleepRaw(date)
daily.period_windows?.[trendRange]
daily.days
```

- [ ] **Step 6: Repeat the same migration for skin temperature**

Use:

```ts
type SkinTempDailyResponse
api.getSkinTempDaily()
api.getSkinTempRaw(date)
daily.period_windows?.[trendRange]
daily.days
daily.daily.map((d) => d.skin_temp)
```

- [ ] **Step 7: Repeat the same migration for heart rate**

Use:

```ts
type HeartRateDailyResponse
api.getHeartRateDaily()
daily.period_windows?.[trendRange]
daily.days
daily.daily
```

Keep `api.getHeartRateAnalysis()`, `api.getHeartRateInsights(date)`, `api.getHeartRateRaw(date)`, and `api.getHRDistribution(date)` unchanged.

- [ ] **Step 8: Repeat the same migration for HRV**

Use:

```ts
type HrvDailyResponse
api.getHrvDaily()
api.getHrvRaw(date)
daily.period_windows?.[trendRange]
daily.days
daily.daily
```

Keep `api.getHrvAnalysis()`, `api.getHrvInsights(date)`, and `api.getDashboardOverview()` unchanged.

- [ ] **Step 9: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected result: all migrated pages compile.

---

## Task 8: Extract Frontend Helpers After The Data Shape Is Stable

**Files:**
- Create: `frontend/src/lib/metric-page.ts`
- Modify: metric pages only where helper use removes exact duplication

- [ ] **Step 1: Add shared selected-date loader for multi-resource days**

Create `frontend/src/lib/metric-page.ts`:

```ts
type MultiDateLoaderOptions<T> = {
	setSelectedDate: (date: string) => void;
	setHistoryOpen?: (open: boolean) => void;
	clearData: () => void;
	fetchByDate: (date: string) => Promise<T>;
	setData: (data: T) => void;
	setError: (message: string) => void;
};

export function createMultiDateLoader<T>(
	options: MultiDateLoaderOptions<T>
): (date: string) => Promise<void> {
	let requestId = 0;

	return async (date: string) => {
		options.setSelectedDate(date);
		options.setHistoryOpen?.(date !== '');
		options.clearData();
		const currentRequest = ++requestId;

		if (!date) {
			return;
		}

		try {
			const data = await options.fetchByDate(date);
			if (currentRequest !== requestId) {
				return;
			}
			options.setData(data);
		} catch (error: unknown) {
			if (currentRequest !== requestId) {
				return;
			}
			options.setError(error instanceof Error ? error.message : String(error));
		}
	};
}
```

- [ ] **Step 2: Use the helper in heart-rate and HRV pages**

For heart rate, fetch the selected day as one object:

```ts
type HeartRateSelectedDayData = {
	insights: HeartRateInsights;
	intraday: HeartRateRawData;
	distribution: HRDistribution;
};
```

Use:

```ts
const onDateChange = createMultiDateLoader<HeartRateSelectedDayData>({
	setSelectedDate: (date) => { selectedDate = date; },
	setHistoryOpen: (open) => { historyOpen = open; },
	clearData: () => {
		historicalInsights = null;
		historicalIntraday = null;
		historicalDistribution = null;
	},
	fetchByDate: async (date) => {
		const [insights, intraday, distribution] = await Promise.all([
			api.getHeartRateInsights(date),
			api.getHeartRateRaw(date),
			api.getHRDistribution(date)
		]);
		return { insights, intraday, distribution };
	},
	setData: (data) => {
		historicalInsights = data.insights;
		historicalIntraday = data.intraday;
		historicalDistribution = data.distribution;
	},
	setError: (message) => { error = message; }
});
```

For HRV, use the same helper with `HrvInsights`.

- [ ] **Step 3: Leave chart configs local unless duplication is exact**

Do not extract the heart-rate and HRV chart configurations in this pass. They have enough metric-specific behavior that a shared abstraction would hide important differences.

- [ ] **Step 4: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected result: all frontend checks pass.

---

## Task 9: Update Docs And Run Full Validation

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Update route docs**

In `README.md` and `docs/ARCHITECTURE.md`, document:

- Metric detail pages now use metric-scoped daily endpoints.
- `/api/daily-aggregates` remains the full daily metric mart endpoint.
- Sleep, HRV, and skin temperature use canonical `/raw` endpoints; the old ambiguous base raw routes are removed.
- Frontend API wrappers use OpenAPI `paths` typing through `openapi-fetch`.

- [ ] **Step 2: Run backend validation**

Run:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

Expected result: all commands pass with zero errors.

- [ ] **Step 3: Run frontend validation**

Run:

```bash
cd frontend && npm run check
```

Expected result: Svelte and TypeScript checks pass.

- [ ] **Step 4: Run visual verification**

Start the app:

```bash
cd backend && uv run uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend && npm run dev
```

Use browser MCP tools to inspect:

- `/heart-rate`
- `/hrv`
- `/sleep`
- `/stress`
- `/body-battery`
- `/respiration`
- `/pulse-ox`
- `/skin-temp`

For each page, confirm:

- The page loads without console-visible data errors.
- The trend range picker shows `3M`, `6M`, and `All`.
- Date selector still works.
- Intraday/raw views still load for selected dates.
- Stat cards use the selected period window.
- Charts are nonblank and axes/units remain visible.

---

## Self-Review

- Spec coverage: the plan covers typed endpoint automation, raw route consistency, `1M` removal, metric-scoped daily APIs, frontend migration, docs, backend validation, frontend validation, and visual inspection.
- Placeholder scan: no unresolved placeholder sections remain.
- Type consistency: backend response names match existing Garmin metric contract names, frontend method names map one-to-one to new routes, and `trendRange` keys match backend period-window keys.
