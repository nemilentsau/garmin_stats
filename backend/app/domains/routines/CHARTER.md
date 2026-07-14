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
- Artifact staging.
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
- coach.
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

- Domain routes mount from `backend/app/domains/routines/routes.py`.
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
