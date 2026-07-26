# journal — Charter

**Status:** partial — backend shipped (`/api/checkins`, `/api/notes`); no journal frontend route yet (frontend parked)
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Subjective/user-authored context. This domain owns `/api/checkins` and
`/api/notes`, including daily check-ins and freeform notes that ground Coach
and experiment interpretation. `routes.py` owns HTTP routes; `application/` owns check-in and
note use cases; `dependencies.py` owns the journal repository dependency
protocol; and `adapters.py` owns SQLite journal persistence and recent
check-in caching.

## Owns
- User-authored daily check-ins.
- Freeform notes.
- Journal context read by Coach and experiment analysis.

## Does not own
- Garmin metrics.
- Experiment definitions.
- Coach runtime.
- Analytics computations.

## May import
- Journal repository dependencies.
- Journal-owned contracts.
- `app.infra.cache` and `app.infra.jsonstore` at the persistence boundary
  (`adapters.py`).
- FastAPI and the bootstrap container from `routes.py` only.
- `sqlite3` for owned DDL (`schema.py`).

## Must not import
- Garmin sync.
- Garmin analytics.
- experiments.
- coach.
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
