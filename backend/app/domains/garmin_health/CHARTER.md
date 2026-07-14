# garmin_health — Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

`garmin_health` is the canonical Garmin health data slice. It owns the canonical
Garmin health contracts, deterministic FIT parsing, timestamp normalization into
local time, and pure day-to-daily-metric composition. It is consumed by ingest
persistence, analytics, experiments, and Coach. It has no routes,
repositories, sync workflows, dashboard reads, experiment analysis, or Coach
retrieval logic — those live in the domains that depend on it. Full data topology
and config paths: `docs/reference/data-and-ingest.md`.

## Owns
- Canonical parsed Garmin reading rows and day-level containers.
- Persisted `DailyMetric` contracts and the nullable daily metric stat contracts.
- Garmin-vocabulary daily metric calculators.
- Pure raw-day-to-daily-metric composition.
- The deterministic FIT parser implementation under `infra/fit_parser/`
  (timestamp normalization to local time via `_shift_timestamps`) — the code
  behind the `app.parser` compatibility facade.
- Running-activity contracts (`contracts/activities.py`) and the running-activity
  FIT parser (`infra/fit_parser/activities.py`, `activity_extractors.py`);
  session/lap/series grain; reading (never writing) the `garmin_activities` tree.

## Does not own
- Archive acquisition, watcher/startup ingest orchestration.
- SQLite persistence.
- Dashboard reads, period summaries.
- Experiment analysis or Coach retrieval.
- Frontend presentation or API routing.

## May import
- `app.contracts.base`.
- `app.utils`.
- Its own contracts/domain modules.

## Must not import
- Garmin sync, Garmin analytics, experiments, coach, routines, artifacts,
  journal.
- Infrastructure adapters.
- FastAPI from application (non-route) modules.
- SQLite helpers from application modules.

## Public entrypoints
- Canonical contracts under `app.domains.garmin_health.contracts`.
- Daily metric composition under `app.domains.garmin_health.domain.daily`
  (`compute_daily_metric`, `compute_daily_metrics`).
- Daily metric calculators under `app.domains.garmin_health.domain.daily_metrics`.
- (Parser surface is re-exported through `app.parser`; the implementation lives in
  `infra/fit_parser/` and is owned by the `garmin-data` skill.)

## Key files
- `contracts/readings.py` — parsed reading containers (`DayData`, `DayWellness`,
  `DaySleep`, `DayHrv`, `DaySkinTemp`, and the per-reading models).
- `contracts/daily.py` — `DailyMetric` and nullable daily stat contracts
  (`DailyHeartRateStats`, `DailyHrvStats`, `DailySleepStats`, etc.).
- `domain/daily.py` — pure day→metric composition (`compute_daily_metric[s]`).
- `domain/daily_metrics/` — per-metric calculators (`compute_daily_*`) plus
  Garmin-vocabulary helpers (`compute_hr_zones`, `normalize_hrv_status`,
  `classify_hrv_recovery`, `HR_ZONE_THRESHOLDS`).
- `infra/fit_parser/` — wellness/day decode (`decode.py`, `days.py`,
  `extractors.py`, `files.py`, `timestamps.py`) plus running activity decode
  (`activities.py`, `activity_extractors.py`).
