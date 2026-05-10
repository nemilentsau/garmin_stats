"""SQLite-backed journal repository adapter.

This module is the persistence boundary for user-authored daily check-ins and
freeform notes. It owns journal-specific CRUD and recent-entry caching while
shared SQLite schema initialization remains with app bootstrap.
"""

from __future__ import annotations

from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.infra import cache
from app.infra.jsonstore import JsonStore

_STORE = JsonStore({"daily_checkins", "notes"})


def save_daily_checkin(checkin: DailyCheckIn) -> None:
    """Persist one daily check-in and invalidate the full check-in cache."""
    _STORE.save(
        "daily_checkins",
        checkin.id,
        checkin.model_dump_json(),
        extra_columns={"entry_date": checkin.date},
    )
    cache.evict(cache.DAILY_CHECKINS)


def load_daily_checkins(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[DailyCheckIn]:
    """Load daily check-ins, optionally filtered by date or recent count."""
    if date is None and last_n is None:
        return cache.cached(cache.DAILY_CHECKINS, _fetch_all_daily_checkins)
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _STORE.load_many(
        "daily_checkins",
        DailyCheckIn,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, id",
        last_n=last_n,
    )


def _fetch_all_daily_checkins() -> list[DailyCheckIn]:
    return _STORE.load_many(
        "daily_checkins",
        DailyCheckIn,
        order_by="entry_date, id",
    )


def save_note(note: Note) -> None:
    """Persist one journal note."""
    _STORE.save(
        "notes",
        note.id,
        note.model_dump_json(),
        extra_columns={"entry_date": note.date},
    )


def load_notes(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[Note]:
    """Load journal notes, optionally filtered by date or recent count."""
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _STORE.load_many(
        "notes",
        Note,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, created_at, id",
        last_n=last_n,
    )


class SqliteJournalRepository:
    """Repository adapter wired by bootstrap for journal use cases.

    The adapter exposes the application dependency while keeping table names,
    cache invalidation, and JSON-store query details local to this module.
    """

    def list_checkins(self, *, date: str | None = None) -> list[DailyCheckIn]:
        return load_daily_checkins(date=date)

    def save_checkin(self, checkin: DailyCheckIn) -> None:
        save_daily_checkin(checkin)

    def list_notes(self, *, date: str | None = None) -> list[Note]:
        return load_notes(date=date)

    def save_note(self, note: Note) -> None:
        save_note(note)
