"""SQLite repository adapter for profile configuration."""

from app.infra.database import load_user_profile, save_user_profile
from app.models import UserProfile


class SqliteProfileRepository:
    def get_profile(self, profile_id: str = "default") -> UserProfile | None:
        return load_user_profile(profile_id=profile_id)

    def save_profile(self, profile: UserProfile) -> None:
        save_user_profile(profile)
