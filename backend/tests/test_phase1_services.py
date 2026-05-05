"""Tests for phase 1 foundation services."""

from app.core.profile.application import get_user_profile, update_user_profile
from app.domains.journal.application.checkins import create_checkin, list_checkins
from app.models import DEFAULT_PROFILE_ID, DailyCheckIn, Note, UserProfile


class _FakeProfileRepository:
    def __init__(self):
        self.profile: UserProfile | None = None

    def get_profile(self, profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
        return self.profile

    def save_profile(self, profile: UserProfile) -> None:
        self.profile = profile


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


class TestProfileService:
    def test_update_user_profile_normalizes_to_default_id(self):
        repo = _FakeProfileRepository()

        saved = update_user_profile(repo, UserProfile(id="custom", name="Andrei"))
        loaded = get_user_profile(repo)

        assert saved.id == "default"
        assert loaded is not None
        assert loaded.id == "default"
        assert loaded.name == "Andrei"


class TestCheckinService:
    def test_create_checkin_replaces_existing_day_even_with_different_body_id(self):
        repo = _FakeJournalRepository()

        first = create_checkin(repo, DailyCheckIn(id="first", date="2026-01-15", energy=3))
        second = create_checkin(repo, DailyCheckIn(id="second", date="2026-01-15", energy=5))
        loaded = list_checkins(repo, date="2026-01-15")

        assert first.id == "checkin-2026-01-15"
        assert second.id == "checkin-2026-01-15"
        assert loaded.total == 1
        assert loaded.checkins[0].energy == 5
