"""Profile application tests."""

from app.core.profile.application import get_user_profile, update_user_profile
from app.models import DEFAULT_PROFILE_ID, UserProfile


class _FakeProfileRepository:
    def __init__(self):
        self.profile: UserProfile | None = None

    def get_profile(self, profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
        return self.profile

    def save_profile(self, profile: UserProfile) -> None:
        self.profile = profile


class TestProfileApplication:
    def test_update_user_profile_normalizes_to_default_id(self):
        repo = _FakeProfileRepository()

        saved = update_user_profile(repo, UserProfile(id="custom", name="Andrei"))
        loaded = get_user_profile(repo)

        assert saved.id == "default"
        assert loaded is not None
        assert loaded.id == "default"
        assert loaded.name == "Andrei"
