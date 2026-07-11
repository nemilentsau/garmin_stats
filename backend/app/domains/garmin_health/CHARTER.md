# garmin_health — Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

`garmin_health` is the canonical Garmin health data slice. It owns the canonical
Garmin health contracts, deterministic FIT parsing, timestamp normalization into
local time, and pure day-to-daily-metric composition. It is consumed by ingest
persistence, analytics, experiments, and assistant. It has no routes,
repositories, sync workflows, dashboard reads, experiment analysis, or assistant
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
- Experiment analysis, assistant retrieval.
- Frontend presentation or API routing.

## May import
- `app.contracts.base`.
- `app.utils`.
- Its own contracts/domain modules.

## Must not import
- Garmin sync, Garmin analytics, experiments, assistant, routines, artifacts,
  journal, programs.
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
- `infra/fit_parser/` — `decode.py`, `days.py`, `extractors.py`, `files.py`,
  `timestamps.py`; FIT decode + local-time normalization.

## Verified against code (2026-07-10)
- Public entrypoints match: `contracts/__init__.py` re-exports the reading and
  daily contracts; `domain/daily.py` exposes `compute_daily_metric[s]`;
  `domain/daily_metrics/__init__.py` exposes the `compute_daily_*` calculators.
- Import boundaries match: application/domain modules import only
  `garmin_health.contracts`, `garmin_health.domain.*`, `app.contracts.base`, and
  `app.utils`; no imports of sync/analytics/other domains or FastAPI/SQLite.
- Note vs. ARCHITECTURE.md: the "Owns" bullet in the central Module Ownership
  Charter does not itemize FIT parsing, but the domain description, Project Layout,
  Core Modules (`app/parser.py` facade → `garmin_health/infra/fit_parser/`), and
  the actual `infra/fit_parser/` package confirm the parser is owned here. It is
  listed under Owns above so this charter is not narrower than the code.
- Note: `domain/daily_metrics` intentionally exports domain-bound helper names
  (`normalize_hrv_status`, `compute_hr_zones`, `classify_hrv_recovery`), which per
  the `app/utils/` rule stay domain-local rather than being promoted to utils.
