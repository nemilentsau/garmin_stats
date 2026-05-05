"""Profile API tests."""

import app.core.profile.api as profile_mod
from app.models import UserProfile


class TestProfileApi:
    def test_get_profile_returns_default_profile(self, monkeypatch):
        monkeypatch.setattr(profile_mod, "get_user_profile", lambda *_args: UserProfile())

        profile = profile_mod.get_profile()

        assert profile.id == "default"
