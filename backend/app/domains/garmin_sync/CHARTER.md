# garmin_sync — Charter

**Status:** partial — wellness ingest/download is shipped; running-activity
download + parse is shipped and wired into `workflows.sync_garmin` and startup
reconciliation; associating parsed sessions with routine/experiment cards is
pending, and there is no read API over the new tables.
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

`garmin_sync` is a data-acquisition capability, not a business domain. It keeps the
local Garmin data current: it acquires wellness day archives, extracts and ingests
them into SQLite, tracks ingest status, and orchestrates Garmin Connect downloads.
Since the activity-sync merge it also downloads tracked-session activity FIT/JSON
from Garmin Connect into `data/garmin_activities/` on every sync;
`infra/activity_ingest.py` parses (via `garmin_health.infra.fit_parser`) and
persists those payloads into `running_activity_*`, and both `sync_garmin` and
startup reconciliation now call it after their respective wellness work —
associating sessions with routine/experiment cards is still pending. It stays
policy-only at the package root with concrete Garmin Connect, filesystem,
watcher, clock, and SQLite details isolated under `infra/`. Full data topology and
config paths: `docs/reference/data-and-ingest.md`.

## Owns
- Garmin archive acquisition, ingest status, and manual ingest orchestration.
- Garmin Connect wellness-archive AND tracked-activity download orchestration.
  Activities land in `data/garmin_activities/`.
- The `data/garmin_activities/` day-tree store (`infra/activity_files.py`):
  extracting downloaded activity payloads (bare FIT or ZIP-of-FITs), deriving
  readable filename stems from local start time plus decoded FIT sport/sub_sport,
  writing JSON metadata sidecars, and activity-id idempotence lookups.
- Fingerprint-gated, idempotent running-activity ingest (`infra/activity_ingest.py`):
  parses new `*_running_*.fit` files (via `garmin_health.infra.fit_parser`) and
  writes `running_activity_sessions`/`_laps`/`_series`. Delta by `source_file`
  (downloads are write-once); tolerates a per-file parse failure without
  aborting the batch; invalidates the read cache only when rows were written.
  Called by `workflows.sync_garmin` (immediately after the activity download
  sweep) and by `infra/runtime.run_startup_ingest_if_needed` (unconditionally,
  after the wellness reconciliation block) via `IngestGateway.
  ingest_running_activities`; the engine's own fingerprint gate makes both
  call sites a cheap no-op when the activities tree is unchanged.
- Watcher suspension during sync and affected-date ingest decisions.
- SQLite schema/DDL for the ingested Garmin tables (`infra/../schema.py`): raw
  parsed day tables, the derived `daily_metrics` table, ingest metadata, and
  the session-grain `running_activity_*` tables.

## Does not own
- FIT parsing semantics (owned by `garmin_health`).
- Analytics calculations, dashboard reads, or period summaries.
- Experiment refresh policy, routine scheduling, assistant evidence.
- Frontend presentation.

## May import
- Its own workflow ports, private workflow/runtime helpers, and owned
  ingest/sync contracts.
- SQLite connection primitives, cache invalidation, and event-bus publishing.
- Canonical Garmin health composition (`garmin_health.domain.daily`,
  `garmin_health.contracts`, `garmin_health.infra.fit_parser` — the last is
  infra-to-infra: `activity_ingest.py` calls the running-activity parser
  directly, since garmin_sync owns persistence and garmin_health owns parsing).
- Adapter code under `domains/garmin_sync/infra` for archive extraction, watcher
  control, filesystem writes, clock, SQLite ingest, and Garmin Connect
  login/download details.
- `app.core.config` for data-root/token-dir/activities-dir resolution (used by
  the infra factory).

## Must not import
- routines, experiments, assistant, artifacts, journal, programs.
- Garmin analytics application modules.
- FastAPI from application (non-route) modules.
- SQLite helpers from application (non-adapter) modules.

## Public entrypoints
- HTTP routes: `/api/ingest`, `/api/ingest/status`, `/api/ingest/sync`.
- Workflow use cases: `trigger_ingest`, `get_ingest_status`, `sync_garmin`.
- Startup reconciliation: `infra/runtime.run_startup_ingest_if_needed` (wired by
  `bootstrap/process_runtime.py`).

## Key files
- `routes.py` — FastAPI routes for `/api/ingest`, `/status`, `/sync`.
- `workflows.py` — ingest/status/sync orchestration (policy-only; deps injected).
  Sync also sweeps a short activity window (wellness range + a 3-day lookback)
  outside watcher suspension, then runs running-activity ingest right after
  that sweep via `deps.ingest.ingest_running_activities`.
- `dependencies.py` — workflow ports/callables: `GarminSyncDependencies`,
  `IngestGateway` (now including `ingest_running_activities`),
  `GarminDownloadClient`, `GarminClientFactory`, `SyncFileStore`,
  `ActivityFileStore`, `ActivityRef`.
- `contracts.py` — `IngestResult`, `IngestStatus`, `SyncResult` (now carries
  `activities_downloaded/skipped/failed` and `runs_ingested`/
  `runs_ingest_failed`).
- `infra/sqlite_ingest.py` — SQLite ingest/status writes; `DatabaseIngestGateway`
  delegates `ingest_running_activities` to `infra/activity_ingest.py`.
- `infra/activity_ingest.py` — fingerprint-gated running-activity ingest
  (`ingest_running_activities`) into `running_activity_*`.
- `infra/filesystem.py` — archive extraction and FIT source fingerprinting.
- `infra/watcher.py` — one stateful data-directory watcher (suspend/resume/
  mark-synced).
- `infra/runtime.py` — startup archive reconciliation through injected deps,
  then an unconditional `ingest_running_activities` call after the wellness
  block (a no-op when the activities tree is unchanged).
- `infra/garmin_connect.py` — Garmin Connect login/download details (wellness
  archives + activity listing + original activity payloads).
- `infra/activity_files.py` — `data/garmin_activities/` day-tree store.
- `infra/factory.py` — wires the production dependency bundle.
- `schema.py` — SQLite DDL for ingested Garmin tables.

## Verified against code (2026-07-11)
- `infra/activity_ingest.py` added: `ingest_running_activities(activities_dir,
  force=False) -> RunningActivityIngestResult`.
- `schema.py` now creates `running_activity_sessions` (+2 indexes + a unique
  index on `source_file`), `running_activity_laps`, and `running_activity_series`
  alongside the existing day tables.
- `contracts.py` gained `RunningActivityIngestResult`; `app/infra/cache.py`
  gained the `RUNS_SESSIONS` key constant (unused by this domain today — it is
  for a future read-side cache over the new tables).
- Wired in: `IngestGateway.ingest_running_activities` (protocol method) is
  implemented by `DatabaseIngestGateway` (delegates to `infra/activity_ingest.py`)
  and called from two sites — `workflows.sync_garmin` (immediately after
  `_sync_activities`, sourcing `deps.activities_dir`) and
  `infra/runtime.run_startup_ingest_if_needed` (unconditionally, after the
  wellness `check_status`/`ingest_all` block, same `deps.activities_dir`
  source). `GarminSyncDependencies` already carried `activities_dir`
  end-to-end (including `infra/factory.build_garmin_sync_infra`), so no new
  deps field was needed. `SyncResult` gained `runs_ingested`/
  `runs_ingest_failed`, threaded from `RunningActivityIngestResult.
  sessions_ingested`/`files_failed`. Associating parsed sessions with
  routine/experiment cards remains unbuilt.

## Verified against code (2026-07-10)
- Public entrypoints match: `routes.py` exposes `/api/ingest`, `/api/ingest/status`,
  `/api/ingest/sync`; `workflows.py` exposes `trigger_ingest`, `get_ingest_status`,
  `sync_garmin`.
- Activity download-only claim confirmed: `infra/activity_files.py` extracts
  payloads, writes JSON sidecars, and answers idempotence lookups but performs no
  DB ingest; `workflows._sync_activities` only downloads/stores. No activity parse
  path exists.
- `infra/garmin_connect.GarminConnectDownloadClient` implements
  `download_wellness_archive`, `list_activities`, and `download_activity_original`
  — confirming the domain owns both wellness AND activity download.
- Import boundaries match: infra imports `garmin_health.contracts` /
  `garmin_health.domain.daily`, `app.infra` (sqlite/cache), `app.realtime.events`,
  and `app.core.config`; no imports of other product domains or analytics.
- Discrepancy vs. ARCHITECTURE.md: the central "Active service areas" paragraph
  enumerates the `infra/*` files but omits `garmin_sync/schema.py`, which exists
  and owns the SQLite DDL for raw day tables, `daily_metrics`, and `ingest_meta`
  (init via `bootstrap/schema.py`). Recorded here rather than silently dropped.
- Note: `infra/activity_files.py` module-level functions are also consumed by
  `scripts/download_garmin.py` backfills (per its docstring), outside the HTTP
  entrypoints.
