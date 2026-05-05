"""SQLite repository adapter for journal records."""

from __future__ import annotations

from app.infra.database import load_daily_checkins, load_notes, save_daily_checkin, save_note
from app.models import DailyCheckIn, Note


class SqliteJournalRepository:
    def list_checkins(self, *, date: str | None = None) -> list[DailyCheckIn]:
        return load_daily_checkins(date=date)

    def save_checkin(self, checkin: DailyCheckIn) -> None:
        save_daily_checkin(checkin)

    def list_notes(self, *, date: str | None = None) -> list[Note]:
        return load_notes(date=date)

    def save_note(self, note: Note) -> None:
        save_note(note)
