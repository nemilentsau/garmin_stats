"""Daily check-in application tests."""

from app.domains.journal.application.checkins import create_checkin, list_checkins
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)


class _FakeJournalRepository:
    def __init__(self):
        self.checkins: dict[str, DailyCheckIn] = {}

    def list_checkins(self, *, date: str | None = None) -> list[DailyCheckIn]:
        checkins = list(self.checkins.values())
        if date is not None:
            return [checkin for checkin in checkins if checkin.date == date]
        return checkins

    def save_checkin(self, checkin: DailyCheckIn) -> None:
        self.checkins[checkin.date] = checkin

    def list_notes(self, *, date: str | None = None) -> list[Note]:
        return []

    def save_note(self, note: Note) -> None:
        pass


class TestCheckinApplication:
    def test_create_checkin_replaces_existing_day_even_with_different_body_id(self):
        repo = _FakeJournalRepository()

        first = create_checkin(repo, DailyCheckIn(id="first", date="2026-01-15", energy=3))
        second = create_checkin(repo, DailyCheckIn(id="second", date="2026-01-15", energy=5))
        loaded = list_checkins(repo, date="2026-01-15")

        assert first.id == "checkin-2026-01-15"
        assert second.id == "checkin-2026-01-15"
        assert loaded.total == 1
        assert loaded.checkins[0].energy == 5
