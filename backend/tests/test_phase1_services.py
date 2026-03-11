"""Tests for phase 1 foundation services."""

import pytest

import app.infra.database as db
from app.infra import cache
from app.models import DailyCheckIn, UserProfile
from app.services.checkins import create_checkin, list_checkins
from app.services.profile import get_user_profile, update_user_profile


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Use a temporary DB for each test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    cache.invalidate()
    db.init_db()
    yield test_db


class TestProfileService:
    def test_update_user_profile_normalizes_to_default_id(self):
        saved = update_user_profile(UserProfile(id="custom", name="Andrei"))
        loaded = get_user_profile()

        assert saved.id == "default"
        assert loaded.id == "default"
        assert loaded.name == "Andrei"


class TestCheckinService:
    def test_create_checkin_replaces_existing_day_even_with_different_body_id(self):
        first = create_checkin(DailyCheckIn(id="first", date="2026-01-15", energy=3))
        second = create_checkin(DailyCheckIn(id="second", date="2026-01-15", energy=5))
        loaded = list_checkins(date="2026-01-15")

        assert first.id == "checkin-2026-01-15"
        assert second.id == "checkin-2026-01-15"
        assert loaded.total == 1
        assert loaded.checkins[0].energy == 5
