"""Repository contracts for journal use cases."""

from __future__ import annotations

from typing import Protocol

from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)


class JournalRepository(Protocol):
    def list_checkins(self, *, date: str | None = None) -> list[DailyCheckIn]: ...

    def save_checkin(self, checkin: DailyCheckIn) -> None: ...

    def list_notes(self, *, date: str | None = None) -> list[Note]: ...

    def save_note(self, note: Note) -> None: ...
