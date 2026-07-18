# Data Sources and Ingest

**Status:** wellness acquisition/ingest and tracked-activity download are shipped; running parse and training association are shipped; strength/breathing parse is not built.

This is the single source of truth for Garmin data roots, ingest/sync behavior, and runtime path configuration.

## Wellness tree

`data/garmin_health_stats/` contains one `YYYY-MM-DD.zip` archive per recovery date and extracted `YYYY-MM-DD/*.fit` files such as `WELLNESS`, `METRICS`, `SLEEP_DATA`, `SLEEP_DISRUPTIONS`, `HRV_STATUS`, `SKIN_TEMP`, and `NAP`.

Pipeline:

`wellness FIT -> garmin_health parser -> local-time day contracts -> daily metric composer -> raw day tables + daily_metrics`

`garmin_sync` owns acquisition, extraction, persistence, status, watcher behavior, and affected-date decisions. `garmin_health` owns decoding, timestamp normalization, and daily composition.

Downloaded wellness archives are staged and validated before they replace the
current ZIP and extracted day directory. A missing, malformed, or unsafe
replacement leaves the last known-good day intact and is reported as a failed
download; only successfully installed days enter incremental ingest.

## Tracked-activity tree

`data/garmin_activities/` contains one directory per local date. Each tracked activity is stored as `HHMMSS_{sport}_{sub_sport}.fit` plus a JSON Connect sidecar, for example `154911_running_generic.fit` or `104600_training_strength_training.fit`.

The FIT file supplies session/lap/record evidence; the sidecar supplies Connect identifiers and summary context. Garmin sync downloads and deduplicates all tracked sports by activity id.

Running files (`*_running_*.fit`) are fingerprint-gated and parsed on sync and startup into `running_activity_sessions`, `running_activity_laps`, and `running_activity_series`. `/api/activities/runs*` serves them, `/runs` displays them, and Training associates them with `running.v3` occurrences through an injected read port. Full semantics are in [`run-activities.md`](run-activities.md).

Strength and breathing files are downloaded but not parsed, stored in SQLite, served, or associated. The strength implementation contract is [`../future/strength-activities.md`](../future/strength-activities.md).

## Configuration

| Concern | Default | Environment override |
|---|---|---|
| SQLite database | `storage/garmin_stats.db` | `GARMIN_DB_PATH` |
| Wellness tree | `data/garmin_health_stats/` | `GARMIN_DATA_DIR` |
| Activity tree | `data/garmin_activities/` | `GARMIN_ACTIVITY_DATA_DIR` |
| Garmin Connect tokens | `~/.garminconnect` | `GARMINTOKENS` |

Path resolution lives in `backend/app/core/config.py`.

## Commands

- Re-ingest wellness after parser changes: `cd backend && uv run python ../scripts/reingest.py`
- Rebuild running rows after parser changes: `cd backend && uv run python ../scripts/reingest_activities.py`
- Download one activity date: `cd backend && uv run python ../scripts/download_garmin.py --activities --date YYYY-MM-DD`
- Download an inclusive range: `cd backend && uv run python ../scripts/download_garmin.py --activities --from YYYY-MM-DD --to YYYY-MM-DD`
- Backfill the wellness archive range: `cd backend && uv run python ../scripts/download_garmin.py --activities --health-range`
- Sync wellness and recent activities: `POST /api/ingest/sync` or the frontend Sync action.

Normal running ingest never re-parses an existing `source_file`; use the rebuild command after adding or changing parser fields.

## Post-ingest reactions

After both wellness and running ingest succeed, manual Sync invokes an injected no-argument completion callback. When `GARMIN_COACH_WORKER_ENABLED=true`, bootstrap wires it to idempotent Coach review reconciliation (it still runs after a source no-op because local-date eligibility can change independently of file changes); when the flag is `false`, bootstrap wires a noop so disabled deployments never enqueue durable coach jobs nobody consumes. A callback exception is logged and does not fail the sync — `POST /api/ingest/sync` reports the ingest outcome regardless of the callback's own success.

The activity sweep also records durable coverage per local date. Coverage means the Garmin activity listing succeeded and every listed activity was already stored or was downloaded and stored successfully. Any listing, payload, download, or storage failure leaves that date uncovered; a later complete sweep marks it covered. Startup ingest does not create coverage because local files alone cannot prove Garmin Connect was checked.

Coach may infer a missed scheduled run only for a covered past date. Startup and periodic reconciliation can therefore discover real ingested runs immediately without declaring an unsynced date skipped. If a late run appears after a skip was already recorded, the run review becomes canonical and the skip remains stored only as superseded audit evidence; it is omitted from review history and measurement-assessment reads.

Watcher-driven successful wellness ingest invokes a separate bootstrap-composed reaction that refreshes active experiment analyses and, when `GARMIN_COACH_WORKER_ENABLED=true`, reconciles Coach review work. `garmin_sync` imports neither consumer.

## Invariants

- FIT timestamps are shifted to local time during ingest. `utc_offset_hours` carries the offset for display; new timestamp fields must follow the same parser path.
- Period statistics come from raw readings, never averages of daily aggregates.
- Startup/watcher/ingest changes require `missing`, `already in sync`, and `changed` tests, including a second unchanged run that performs no work, plus a real-tree smoke check.
- Cache invalidation occurs only when owned persisted data changes.
- A running-activity tree fingerprint is persisted only after every newly
  discovered running FIT parses successfully. A partial failure leaves the
  previous fingerprint in place so the unchanged tree is retried at the next
  startup or sync.
- Cross-domain reactions remain injected, idempotent, and composed in bootstrap.
