"""SQLite repository adapter for profile configuration."""

from app.core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    UserProfile,
)
from app.infra.database import load_user_profile, save_user_profile


class SqliteProfileRepository:
    def get_profile(self, profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
        return load_user_profile(profile_id=profile_id)

    def save_profile(self, profile: UserProfile) -> None:
        save_user_profile(profile)
