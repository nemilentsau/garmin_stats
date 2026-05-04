# Garmin Analytics Domain Design

Date: 2026-05-03
Status: First slice implemented

## Summary

Create `backend/app/domains/garmin_analytics/` as the backend owner for Garmin-derived analytical read models and analytical use cases.

This domain should start by migrating the existing biometric and recovery dashboard surface. It must also be shaped for future session/activity data, such as runs, meditations, and strength sessions, without prematurely parsing or modeling those activity files in this slice.

The important design rule is that `DailyMetric` is one read-model family inside Garmin analytics. It is not the domain itself.

## Implementation Status

The first biometric-focused slice has been implemented on 2026-05-03.

What landed:

- `backend/app/domains/garmin_analytics/` now owns dashboard overview, raw wellness, sleep, HRV, skin temperature, daily aggregates, windowed period summaries, and recovery insight/analysis implementations.
- `backend/app/bootstrap/routing.py` mounts the domain-local Garmin analytics routers directly.
- Flat routers for the migrated endpoints now act as compatibility wrappers.
- `backend/app/domains/garmin_analytics/api/insights.py` owns heart-rate, stress, and body-battery insight/analysis routes.
- `backend/app/domains/garmin_analytics/application/insights.py` is a route-facing facade over domain-local metric-analysis modules.
- Flat metric-analysis services under `backend/app/services/` now delegate to domain-local Garmin analytics implementations.
- `backend/app/services/dashboard.py` delegates to the domain implementation.
- `backend/app/services/period_windows.py` was removed; period summaries now live in `backend/app/domains/garmin_analytics/application/period_summary.py`.
- `backend/app/bootstrap/container.py` exposes a domain-local biometric repository.
- Architecture guards prevent migrated API modules from importing global database helpers or `stats.py` directly.
- `/api/days` remains outside the domain.
- Activity/session ownership remains documented but unimplemented.

## Context

The backend refactor is moving from flat routers and services into a domain-modular monolith. `routines` and `assistant` have already established the pattern of domain-local `api`, `application`, `domain`, and `infra` packages.

At the start of this slice, the Garmin analytics surface was mostly flat:

- `backend/app/routers/dashboard.py`
- `backend/app/routers/wellness.py`
- `backend/app/routers/sleep.py`
- `backend/app/routers/hrv.py`
- `backend/app/routers/skin_temp.py`
- `backend/app/routers/daily_aggregates.py`
- `backend/app/routers/heart_rate.py`
- `backend/app/routers/stress.py`
- `backend/app/routers/body_battery.py`
- `backend/app/services/dashboard.py`
- `backend/app/services/period_windows.py`
- metric analysis services under `backend/app/services/`
- shared analytical helpers in `backend/app/stats.py`

The repo also has early activity-analytics design work in `docs/ACTIVITY_ANALYTICS_DESIGN.md`, plus example running archives under `data/running/`. Those files are useful as boundary constraints, but proper activity parsing and mart design requires Garmin SDK exploration and data analysis. That is outside this migration slice.

## Goals

- Move the current biometric/recovery read surface into a real `garmin_analytics` domain.
- Preserve current HTTP routes and response contracts during this phase.
- Remove obvious router-to-database and router-to-`stats.py` shortcuts for migrated endpoints.
- Introduce a domain-local repository boundary for Garmin biometric reads.
- Keep the domain ready for heterogeneous read-model families:
  - daily biometric summaries
  - raw biometric streams
  - future session/activity marts
  - future custom analyst-derived metrics
- Make it explicit that activity/session data should not be collapsed into `DailyMetric`.

## Non-Goals

- Do not parse `data/running` in this slice.
- Do not add run, meditation, or strength session marts yet.
- Do not redesign the frontend dashboard or route UX.
- Do not change public API contracts unless a route is objectively broken.
- Do not move ingest, watcher, archive extraction, or parser startup logic into this domain.
- Do not migrate every metric insight service in the first slice.

## Domain Boundary

`garmin_analytics` owns Garmin-derived analytical read models and analytical use cases:

- dashboard overview
- biometric read APIs
- period summaries and time-window analytics
- backend-derived insights and analysis endpoints
- future activity/session marts
- future custom analyst metrics

It does not own:

- ingest orchestration
- archive watching or extraction
- parser startup checks
- raw file catalog behavior
- assistant-specific retrieval logic

`/api/days` should stay outside the first `garmin_analytics` slice. It currently describes ingested file availability and parser summaries, so it is closer to ingest/data-catalog ownership than analytical read-model ownership.

## Target Package Shape

```text
backend/app/domains/garmin_analytics/
  api/
    overview.py
    biometrics.py
    insights.py
  application/
    overview.py
    biometrics.py
    period_summary.py
    insights.py
    heart_rate.py
    heart_rate_analysis.py
    hrv.py
    hrv_analysis.py
    sleep_analysis.py
    stress_analysis.py
    body_battery_analysis.py
    ports.py
  domain/
    biometrics.py
    sessions.py
    windows.py
  infra/
    biometric_repository.py
```

### `api`

Owns FastAPI route handlers for migrated Garmin analytics endpoints. Route handlers should remain thin: parse HTTP input, call application use cases, and return Pydantic response models.

The HTTP paths remain stable. The domain package changes internal ownership, not frontend contracts.

### `application`

Owns use cases and orchestration.

- `overview.py` owns dashboard composition currently in `services/dashboard.py`.
- `biometrics.py` owns raw biometric read use cases for wellness, sleep, HRV, skin temperature, and daily aggregates.
- `period_summary.py` owns windowed period summaries currently in `services/period_windows.py`.
- `insights.py` is the route-facing facade for analysis endpoints.
- `heart_rate.py`, `heart_rate_analysis.py`, `hrv.py`, `hrv_analysis.py`, `sleep_analysis.py`, `stress_analysis.py`, and `body_battery_analysis.py` own the current recovery analysis implementations.
- `ports.py` defines read interfaces for biometric data and future session/activity data.

### `domain`

Owns pure analytical concepts that should not depend on FastAPI or SQLite.

- `biometrics.py` describes biometric read-model concepts.
- `windows.py` owns reusable windowing concepts.
- `sessions.py` reserves the activity/session boundary. Tracked Garmin activities are session-grain analytical records, not daily metric fields.

### `infra`

Owns SQLite-backed repository implementations and any other persistence adapters for the domain.

The first repository should wrap current shared read helpers from `app.infra.database` behind a domain-local interface. This is a migration step away from routers and application code calling the global database module directly.

## First Migration Slice

The first slice should move the foundation and current biometric read surface:

1. Create the `garmin_analytics` domain package.
2. Add a biometric repository interface and SQLite-backed implementation.
3. Move dashboard overview use cases.
4. Move daily aggregates and period-window summaries.
5. Move raw biometric endpoints:
   - `/api/wellness`
   - `/api/sleep`
   - `/api/hrv`
   - `/api/skin-temp`
   - `/api/daily-aggregates`
6. Mount the domain-local routers from `bootstrap/routing.py`.
7. Keep old flat routers only as temporary compatibility wrappers where useful.
8. Add architecture guards for the migrated domain.

This slice should not move:

- `/api/days`
- heart-rate insights, analysis, or distribution
- HRV insight and analysis endpoints beyond preserving the existing raw HRV route behavior
- stress analysis
- body-battery analysis
- sleep analysis if moving it would force the slice to absorb the heavier insight layer too early
- activity/session parsing

## Future Activity And Session Boundary

The domain must be ready for activity/session analytics without implementing them now.

The long-term analytical model should distinguish:

- biometric/recovery data: daily summaries and raw biometric streams
- activity/session data: run, meditation, strength, and other tracked-session records
- custom analyst metrics: derived metrics that may compose across biometrics, sessions, experiments, routines, notes, and check-ins

Activity sessions should not be forced into `DailyMetric` just because the current dashboard is daily-grain. Later activity work should add dedicated session marts and repositories under `garmin_analytics`.

This matters for the analyst-agent direction: the assistant should eventually retrieve from multiple analytical marts instead of relying on one daily aggregate shape.

## Dependency Rules

For migrated code:

- `garmin_analytics/api` may import FastAPI and `garmin_analytics/application`.
- `garmin_analytics/api` must not import `app.infra.database` or `app.stats`.
- `garmin_analytics/application` must remain FastAPI-free.
- `garmin_analytics/application` must not import flat `app.services.*` modules or `app.infra.database`; use application ports instead.
- `garmin_analytics/domain` must not import FastAPI, SQLite, global database helpers, or sibling domain internals.
- `garmin_analytics/infra` may depend on shared database primitives and Pydantic read models.

## Testing Strategy

The first implementation plan should include:

- route contract tests for moved endpoints
- application tests for dashboard overview, daily aggregates, period summaries, and raw biometric reads
- repository tests proving reads go through the domain-local repository
- architecture guard tests:
  - `api` does not import `app.infra.database` or `app.stats`
  - `application` is FastAPI-free
  - compatibility wrappers remain thin
- full backend verification:
  - `cd backend && uv run ruff check`
  - `cd backend && uv run pyright app/ tests/`
  - `cd backend && uv run pytest tests/ -v`

If backend API schema changes unexpectedly, regenerate TypeScript API types with `bash scripts/generate-api-types.sh` and verify the frontend.

## Definition Of Done

- `backend/app/domains/garmin_analytics/` exists with the agreed package structure.
- Current HTTP behavior is preserved for the migrated endpoints.
- Migrated API modules no longer import global database helpers or `stats.py` directly.
- The first biometric repository boundary exists.
- `/api/days` remains outside this slice.
- Activity/session ownership is documented as future `garmin_analytics` work.
- Backend lint, type check, and tests pass.
