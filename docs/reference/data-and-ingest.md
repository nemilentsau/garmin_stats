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

Sync ingests the union of the days it downloaded and the days whose archives its
extraction step refreshed. The second half matters for archives replaced outside
the app: file events are dropped while sync holds the watcher suspended, so a day
that sync extracted but never ingested would keep stale rows behind a whole-tree
fingerprint that says everything is current.

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
- Preview the failed-round Coach/training reset:
  `cd backend && uv run python ../scripts/reset_failed_round.py`
- Execute that reset after stopping the app:
  `cd backend && uv run python ../scripts/reset_failed_round.py --execute`.
  It clears imported training state and Coach state, removes the Coach runtime
  directory, and verifies every non-reset, non-retired SQLite table plus both Garmin
  source trees remain byte-for-byte unchanged. Goals, experiments, exposures, analyses,
  reports, profile, notes, check-ins, and Garmin data are preserved. The runtime path is
  fixed to the database's `coach/` sibling and must be disjoint from both Garmin trees.
  The command fails closed unless the database already exists and contains the
  Garmin Stats schema markers; authored bundle files are outside the reset.

Normal running ingest re-parses only new or source-signature-changed files; use
the rebuild command after parser changes that do not alter the source signature.

## Post-ingest reactions

Manual sync and startup ingest update Garmin-owned data and publish their normal
data-change events; neither creates Coach work. Coach reviews are manual-only and
independent of activity coverage, upload timing, and schedule dates.

Successful manual ingest, manual sync, startup reconciliation, and watcher-driven
wellness ingest invoke one bootstrap-composed reaction that refreshes active
experiment analyses. The reaction is best-effort so a read-model refresh failure
does not falsify a successful Garmin ingest. `garmin_sync` does not import that
consumer.

## Invariants

- FIT timestamps are shifted to local time during ingest; new timestamp fields must follow the same parser path. A day can hold more than one offset — DST rollover or travel, sometimes changing inside a single WELLNESS file — so each reading is shifted with the offset in effect at its own instant, taken from its own source file. The day's `utc_offset_hours` is the offset in effect at the end of that day, and is a display label, not the shift that was applied to every reading.
- Period statistics come from raw readings, never averages of daily aggregates.
- Startup/watcher/ingest changes require `missing`, `already in sync`, and `changed` tests, including a second unchanged run that performs no work, plus a real-tree smoke check.
- Cache invalidation occurs only when owned persisted data changes.
- A running-activity tree fingerprint is persisted only after every newly
  discovered running FIT parses successfully. A partial failure leaves the
  previous fingerprint in place so the unchanged tree is retried at the next
  startup or sync.
- Cross-domain reactions remain injected, idempotent, and composed in bootstrap.
