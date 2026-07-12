# Data Sources & Ingest

**Status:** shipped (wellness ingest + activity download) · **shipped for running** (activity parse + prescription association; see `run-activities.md`) · **partial** (strength/breathing parse — pending, spec in `../future/`)

Single source of truth for *what Garmin data the app has, where it lives, and how it gets in*. If you touch data roots, ingest, sync, the watcher, or config paths, update this file in the same change. CLAUDE.md and README point here rather than restating any of it.

## Two data trees

The app draws on **two separate local trees**. They are different shapes with different lifecycles — do not conflate them.

### 1. `data/garmin_health_stats/` — wellness/monitoring (INGESTED)

- **Shape:** one archive per day, `YYYY-MM-DD.zip`, extracted to `YYYY-MM-DD/*.fit`. Flat zips of `{id}_{TYPE}.fit` files: `WELLNESS`, `METRICS`, `SLEEP_DATA`, `SLEEP_DISRUPTIONS`, `HRV_STATUS`, `SKIN_TEMP`, `NAP`. All day-grain overnight/all-day signals.
- **Pipeline (built):** `FIT files → garmin_health FIT parser → daily metric composer → SQLite` (`daily_metrics` + raw `wellness_data`/`sleep_data`/`hrv_data`/`skin_temp_data`). Owned by `garmin_sync` (acquisition/ingest) + `garmin_health` (parse/compose).
- **This is the only tree the DB currently reads from.**

### 2. `data/garmin_activities/` — tracked sessions (DOWNLOADED; RUNNING PARSED, STRENGTH/BREATHING NOT YET)

- **Shape:** one directory per day, `YYYY-MM-DD/`, holding per-activity pairs `HHMMSS_{sport}_{sub_sport}.fit` + `HHMMSS_{sport}_{sub_sport}.json` (Garmin Connect summary sidecar). e.g. `154911_running_generic.fit`, `104600_training_strength_training.fit`, `131800_training_breathing.fit`.
- **Content:** the raw FIT carries full `session` / `lap` / `record` messages — per-second HR/pace/cadence/power, splits, GPS. The JSON sidecar carries the Connect summary (distance, duration, training effect/load, power zones, `activityId`, `startTimeLocal`). ~1,100+ files on disk (~290+ running, plus strength/breathing/yoga). HR is present in runs from ~March 2026 onward (date-patterned — see `run-activities.md`).
- **Acquisition (built):** pulled from Garmin Connect on **every sync** and by backfill. `garmin_sync/infra/garmin_connect.py` logs in and downloads activity originals; `garmin_sync/workflows.py::sync_garmin` sweeps a recent-activity window; `garmin_sync/infra/activity_files.py` (`FilesystemActivityStore`) extracts each payload into the day tree, writes the JSON sidecar, and dedups by `activityId`. Manual backfill: `scripts/download_garmin.py --activities`.
- **Parse (shipped for running; strength/breathing NOT built):** running FIT files (`*_running_*.fit`) parse into `running_activity_sessions`/`running_activity_laps`/`running_activity_series` on every sync and at startup, gated by a whole-tree fingerprint (`ingest_meta` key `activities_fingerprint`) so an unchanged activities tree is a no-op. Served by `/api/activities/runs*` and displayed at `/runs` + `/runs/[id]` — strap channels (GCT balance, respiration, stance time), stamina/performance-condition, and a GPS route map included. Full detail — parser/store/serve/display, `hr_source` semantics, units, known gaps — is `run-activities.md`. A tracked run can also be linked to the `running.v3` prescription card it satisfies, surfaced on the Today board (`training` domain policy over `garmin_analytics` data via an injected port; see `run-activities.md` "Association" and `training/CHARTER.md`) — this closes roadmap next-step #1's running half; manual objective-run capture (self-reported distance/time on a card) is superseded by it. Strength and breathing FIT files still download but are not parsed: no metrics extracted, no table, no route, no association. Strength parse design: `../future/STRENGTH_ACTIVITY_SCHEMA.md`; broader activity-mart design: `../future/ACTIVITY_ANALYTICS_DESIGN.md`.

## Configuration (`backend/app/core/config.py`)

| Concern | Default | Env override |
|---|---|---|
| SQLite DB | `storage/garmin_stats.db` | `GARMIN_DB_PATH` |
| Wellness tree | `data/garmin_health_stats/` | `GARMIN_DATA_DIR` |
| Activities tree | `data/garmin_activities/` | `GARMIN_ACTIVITY_DATA_DIR` |
| Garmin Connect tokens | `~/.garminconnect` | `GARMINTOKENS` |

## Commands

- **Re-ingest wellness after parser changes:** `cd backend && uv run python ../scripts/reingest.py`
- **Re-ingest running activities after parser changes:** `cd backend && uv run python ../scripts/reingest_activities.py` (wipes `running_activity_*` + the `activities_fingerprint` meta key, then re-parses every file — see `run-activities.md`)
- **Download tracked activities (backfill):** `cd backend && uv run python ../scripts/download_garmin.py --activities …` (see README "Data And Ingest" for `--date` / `--from`/`--to` / `--health-range`)
- **Sync (wellness archives + activities):** `POST /api/ingest/sync` (also the frontend sync button)

After both wellness and running-activity ingest succeed, sync invokes a generic
bootstrap-supplied callback. Bootstrap uses it to reconcile idempotent coach review work;
the sync domain imports no coach symbols. An unchanged sync still invokes the callback
because local-date eligibility can change while the source tree does not. Watcher-driven
successful ingest runs the same composition alongside experiment-analysis refresh. When
`GARMIN_COACH_WORKER_ENABLED=false`, bootstrap skips coach reconciliation and execution.

## Invariants (for code that touches this path)

- **Timestamps are local time.** FIT files store UTC; the parser extracts the per-day UTC offset from `monitoring_info_mesgs` and shifts all timestamps to local at ingest (`DayData.utc_offset_hours` / `DailyMetric.utc_offset_hours` carry it for display). New timestamp fields must be shifted at ingest — see the `garmin-data` skill for the parser internals.
- **Period-level stats come from raw readings**, never from averaging daily aggregates.
- **Watcher/startup/ingest changes must prove no-op behavior:** touching startup ingest, archive extraction, watcher logic, cache invalidation, or data-root resolution requires tests covering `missing`, `already in sync`, and `stale/changed`, including an idempotence case where a second run with no file changes does no work — then a real local smoke check against the actual data tree.
- **Post-ingest reactions must remain injected and idempotent.** `garmin_sync` calls a no-argument capability only after both ingest paths succeed; cross-domain reaction composition stays in bootstrap. Repeated successful callbacks may do no work.
