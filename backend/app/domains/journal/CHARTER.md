# journal — Charter

**Status:** partial — backend shipped (`/api/checkins`, `/api/notes`); no journal frontend route yet (frontend parked)
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Subjective/user-authored context. This domain owns `/api/checkins` and
`/api/notes`, including daily check-ins, freeform notes, and future
journal-style context that can ground assistant coaching and experiment
interpretation. `routes.py` owns HTTP routes; `application/` owns check-in and
note use cases; `dependencies.py` owns the journal repository dependency
protocol; and `adapters.py` owns SQLite journal persistence and recent
check-in caching.

## Owns
- User-authored daily check-ins.
- Freeform notes.
- Journal context that can later be read by assistant or experiment
  interpretation.

## Does not own
- Garmin metrics.
- Routine execution.
- Experiment definitions.
- Assistant runtime.
- Analytics computations.

## May import
- Journal repository dependencies.
- Journal-owned contracts.

## Must not import
- Garmin sync.
- Garmin analytics.
- routines.
- experiments.
- assistant.
- artifacts.
- FastAPI from application modules.
- SQLite helpers from application modules.

## Public entrypoints
- `/api/checkins` (list/filter-by-date, create-or-replace).
- `/api/notes` (list/filter-by-date, create).
- Check-in use cases and note use cases called by those routes.

## Key files
- `routes.py` — FastAPI boundary mounting `checkins_router` (`/api/checkins`)
  and `notes_router` (`/api/notes`).
- `application/` — `checkins.py`, `notes.py`.
- `dependencies.py` — `JournalRepository` port.
- `adapters.py` — SQLite journal persistence and recent check-in caching
  (`SqliteJournalRepository`).
- `contracts.py` — `DailyCheckIn`, `Note`, and their list responses.
- `schema.py` — SQLite table schema for journal storage.

## Verified against code (2026-07-10)
- Matches. Owns, does-not-own, may-import, public entrypoints, and the
  route prefixes (`/api/checkins`, `/api/notes`) all match the code.
- Import boundary is clean: the only non-journal imports are
  `app.infra.jsonstore` and `app.infra.cache` in `adapters.py` (the adapter
  layer; `app.infra.cache` backs the "recent check-in caching" the charter
  names). No cross-domain imports and no FastAPI/SQLite-helper imports from
  application modules.
- Status note: backend routes and use cases are shipped, but there is no
  frontend route for check-ins/notes yet (the frontend route list has no
  journal surface), so the read-by-assistant/experiment consumers remain the
  primary intended readers.
