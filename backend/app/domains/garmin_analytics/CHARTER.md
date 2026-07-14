# garmin_analytics — Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

`garmin_analytics` owns Garmin-derived analytical read models and dashboard use
cases. It is biometric-first but not `DailyMetric`-only: it serves the dashboard
overview, full and metric-scoped daily metric responses, period summaries,
metric-specific raw biometric reads, the current metric analysis and
selected-day insight implementations for heart rate, HRV, sleep, stress, and body
battery, and the runs activity mart (list/detail/series reads over the
running-activity tables `garmin_sync` ingests). It is a read/analytical layer over
ingested Garmin tables — it acquires no data and normalizes no timestamps.
Strength sessions are not yet parsed; their retained implementation contract is
`docs/future/strength-activities.md`.

## Owns
- Garmin-derived read models and biometric API reads.
- Dashboard overview (recovery state, score trajectory, evidence, health flags).
- Daily metric API response wrapping and period summaries.
- Metric drill-down insights and recovery analysis responses.
- The validated single-axis recovery score and its health flags
  (`domain/recovery_score/`).
- The runs activity mart: run list/detail/series reads with backend-derived pace,
  imperial values, chart-valid series, and user-facing FIT zone projections
  (`application/runs.py`, `domain/run_display.py`, `contracts/runs.py`,
  `SqliteRunsRepository`).

## Does not own
- Archive acquisition (owned by `garmin_sync`).
- Parser timestamp normalization (owned by `garmin_health`).
- Routine execution.
- Canonical daily metric composition (owned by `garmin_health`).
- Experiment exposure derivation.
- Coach runtime behavior.
- Subjective journal writes.

## May import
- Its repository dependency protocols (`application/dependencies.BiometricReadRepository`,
  `application/dependencies.RunsReadRepository`).
- Garmin analytics domain helpers.
- Garmin analytics contracts.
- Canonical Garmin health contracts/calculators.
- Domain-agnostic helpers from `app.utils`.
- (`adapters.py` only: `app.infra.sqlite` / `app.infra.cache` at the persistence
  boundary.)

## Must not import
- Garmin sync, routines, experiments, coach, artifacts, journal.
- FastAPI from application (non-route) modules.
- SQLite helpers from application (non-adapter) modules.

## Public entrypoints
Dashboard, daily metric, and metric-scoped raw/daily/analysis/insight API routes
for sleep, HRV, skin temperature, heart rate, stress, body battery, respiration,
and pulse ox — specifically:
- `/api/dashboard`, `/api/daily-aggregates`
- `/api/sleep/{raw,daily,analysis}`
- `/api/hrv/{raw,daily,analysis,insights}`
- `/api/skin-temp/{raw,daily}`
- `/api/heart-rate/{raw,daily,analysis,insights,distribution}`
- `/api/stress/{raw,daily,analysis}`
- `/api/body-battery/{raw,daily,analysis}`
- `/api/respiration/{raw,daily}`
- `/api/pulse-ox/{raw,daily}`
- `/api/activities/runs`, `/api/activities/runs/{run_id}`, `/api/activities/runs/{run_id}/series`

Application files are named by concern:
- `raw_biometrics.py` — reads raw biometric tables.
- `daily_aggregates.py` — wraps persisted daily metrics and computes period windows.
- `dashboard.py` — loads overview inputs.
- `metric_analysis.py` — loads cached chart/trend analysis read models.
- `metric_insights.py` — loads selected-day insight read models.
- `runs.py` — run list/detail/series reads with date-window filtering and
  display projection.

## Key files
- `routes.py` — HTTP only; binds request/response to application use cases.
- `application/` — orchestration only: loads repository data, handles route-level
  missing-data decisions, applies caching, delegates calculations.
- `application/dependencies.py` — `BiometricReadRepository` and
  `RunsReadRepository` read ports.
- `adapters.py` — SQLite biometric and runs read repositories (persistence
  wiring; `SqliteBiometricRepository`, `SqliteRunsRepository`).
- `domain/aggregates/` — deterministic period response shaping; `period_metrics/`
  owns metric-specific period rules from raw readings (period stats never from
  averaged daily summaries).
- `domain/analysis/` — chart/trend analysis calculations.
- `domain/insights/` — selected-day insight calculations.
- `domain/primitives/` — generic numeric/window/timestamp/trend helpers.
- `domain/recovery_score/` — normalization, weighting, smoothing, thresholds,
  flags, regimes, evidence (each pure, unit-tested).
- `domain/dashboard.py` — maps recovery score onto `DashboardOverviewResponse`.
- `contracts/` — API/read-model contracts split by concern (`raw`, `period`,
  `analysis`, `insights`, `dashboard`).
