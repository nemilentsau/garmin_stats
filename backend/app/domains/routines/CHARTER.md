# routines — Charter

**Status:** shipped (backend + `/today` and `/routines/schedule` frontend routes); legacy v2 runtime — the active training path is the standalone `training` slice
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Routine catalog, schedule projection, activation, and Today execution. This
slice uses a flat small-capability layout: `routes.py` owns `/api/routines`
and `/api/today`; `application/` owns use cases for catalog, activation,
schedule, and today; `schedule.py` owns pure schedule helpers;
`dependencies.py` owns repository/observer/callable dependencies;
`adapters.py` owns the SQLite repository adapter; and `contracts.py` owns
routine API/persistence/activation command shapes.

## Owns
- Routine catalog reads.
- Routine activation.
- Assignment projection.
- Today card presentation.
- Today log writes.

## Does not own
- Assistant artifact staging.
- Experiment analysis.
- Garmin ingest.
- Garmin analytics.

## May import
- Its own pure schedule helpers.
- Routine dependencies.
- Routine-owned contracts.

## Must not import
- artifacts.
- experiments.
- assistant.
- Garmin sync.
- Garmin analytics.
- FastAPI from application modules.
- SQLite helpers from application modules.

## Public entrypoints
- `/api/routines` (catalog list, schedule-window, routine detail, and
  routine assignments).
- `/api/today` (Today board read, card-log range read, and Today card-log
  upsert).
- Schedule-window use cases and Today log use cases called by those routes.

## Routine Runtime Boundary

Legacy boundary for v2 routine bundles (meditation, breathwork); the active
training path is the standalone `training` slice (see its charter).

- Domain routes now mount from `backend/app/domains/routines/routes.py`.
- `/routines/schedule` handles routine review and bundle import.
- `/today` reads one day of live compiled occurrences and writes logs only.

Normal bundle flow:

`bundle JSON -> preview -> import -> auto-activate -> live schedule/today`

Important rules:

- preview performs no writes;
- bundle import persists artifacts and auto-activates them;
- Today does not create schedule structure;
- schedule exceptions are still read for backward compatibility, but Today does
  not author them.

## Key files
- `routes.py` — FastAPI boundary mounting `routines_router` (`/api/routines`)
  and `today_router` (`/api/today`).
- `application/` — `catalog.py`, `activation.py`, `schedule_window.py`,
  `today.py`.
- `schedule.py` — pure schedule projection helpers.
- `dependencies.py` — `RoutineRepository` port, `TodayCardLogObserver` port,
  and `CardTemplateDependencyActivator` callable.
- `adapters.py` — SQLite repository (`SqliteRoutineRepository`).
- `contracts.py` — routine API, persistence, and activation-command shapes
  (routine schedules, assignments, cards, overrides, logs, Today, activation
  command).
- `schema.py` — SQLite table schema for routine storage.

## Verified against code (2026-07-10)
- Owns, does-not-own, may-import, and public entrypoints match the code.
- `routes.py` mounts only `/api/routines` and `/api/today`. The central
  "Routine runtime" route-inventory block also lists `/api/cards`, but that
  route is owned by the `artifacts` domain — it is not mounted here.
- Import boundary holds: no module under `routines/` imports artifacts,
  experiments, assistant, Garmin sync, or Garmin analytics. The Today card-log
  upsert notifies experiment exposure sync through the injected
  `TodayCardLogObserver` (wired at the composition root / container), not a
  direct import — consistent with "Must not import experiments".
- Routine activation is owned here (`application/activation.py`); the
  `artifacts` domain delegates live routine activation writes into this slice,
  matching the artifacts charter.
- `adapters.py` imports `app.infra.sqlite` / `app.infra.jsonstore` (adapter
  layer, allowed); application modules do not import FastAPI or SQLite helpers.
- Bundle preview/import is not a `routines/routes.py` endpoint; the Routine
  Runtime Boundary's "import -> auto-activate" flow is driven by the
  artifacts/training import paths that then activate through this slice.
