"""Dependencies consumed by journal application use cases.

Journal workflows persist user-authored check-ins and freeform notes through
this protocol. Concrete SQLite details, cache behavior, and query ordering
belong in the adapter layer.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)


class JournalRepository(Protocol):
    """Persistence dependency for dated check-ins and notes."""

    def list_checkins(
        self,
        *,
        date: str | None = None,
        last_n: int | None = None,
    ) -> list[DailyCheckIn]: ...

    def save_checkin(self, checkin: DailyCheckIn) -> None: ...

    def list_notes(
        self,
        *,
        date: str | None = None,
        last_n: int | None = None,
    ) -> list[Note]: ...

    def save_note(self, note: Note) -> None: ...
