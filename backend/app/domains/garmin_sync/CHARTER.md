# garmin_sync — Charter

**Status:** partial — wellness acquisition/ingest and tracked-activity download are shipped; running parse/persistence is shipped; strength/breathing parse is not built.
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

`garmin_sync` is a data-acquisition capability, not a business domain. It also
owns persistence for the Garmin data it ingests. Full data roots, lifecycle,
configuration, and commands live in `docs/reference/data-and-ingest.md`.

## Owns

- Garmin Connect wellness-archive and tracked-activity download orchestration.
- Wellness archive extraction, source fingerprinting, affected-date decisions, ingest status, manual ingest, and watcher suspension/resume.
- The tracked-activity filesystem store, JSON sidecars, readable filenames, and activity-id download idempotence.
- Fingerprint-gated running-activity ingest and per-file failure isolation.
- SQLite persistence/schema for raw Garmin day data, derived `daily_metrics`, ingest metadata, and running session/lap/series rows.
- Read-cache invalidation and event publication when owned persisted data changes.
- Invocation of injected sync/watcher completion capabilities; bootstrap owns the cross-domain reaction policy.

## Does not own

- FIT parsing semantics, decoding, or timestamp normalization (`garmin_health`).
- Garmin analytical read models or dashboard calculations (`garmin_analytics`).
- Training prescription association/evaluation (`training`).
- Experiment refresh or Coach reconciliation policy (bootstrap composition).
- Frontend presentation.

## May import

- Its own contracts, workflow ports, and infrastructure adapters.
- Canonical Garmin health contracts, daily composition, and FIT parsing at the ingest boundary.
- Shared SQLite, cache, realtime-event, and configuration primitives from `app.infra`, `app.realtime`, and `app.core.config`.
- FastAPI and the bootstrap container from `routes.py` only.

## Must not import

- Routines, experiments, Coach, artifacts, journal, or Garmin Analytics application modules.
- FastAPI from workflow/infra modules.
- SQLite helpers from workflow modules.

## Public entrypoints

- `/api/ingest`, `/api/ingest/status`, `/api/ingest/sync`.
- `trigger_ingest`, `get_ingest_status`, and `sync_garmin` in `workflows.py`.
- Startup reconciliation through `infra/runtime.run_startup_ingest_if_needed`.

## Key files

- `routes.py` — HTTP binding.
- `workflows.py` — ingest/status/sync orchestration over injected dependencies.
- `dependencies.py` and `contracts.py` — workflow ports and result shapes.
- `infra/garmin_connect.py` and `infra/activity_files.py` — Garmin Connect acquisition and tracked-activity filesystem storage.
- `infra/filesystem.py`, `infra/watcher.py`, and `infra/runtime.py` — extraction/fingerprints, watcher state, and startup reconciliation.
- `infra/sqlite_ingest.py` and `infra/activity_ingest.py` — wellness/running persistence and running ingest.
- `infra/factory.py` — production dependency composition for this capability.
- `schema.py` — owned SQLite DDL.
