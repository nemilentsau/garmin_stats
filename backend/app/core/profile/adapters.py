"""SQLite-backed profile repository adapter.

Profile is core app configuration rather than a product domain, but it still
owns its persistence boundary. This adapter stores JSON-backed profile records
through the shared SQLite connection primitives.
"""

from app.core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    UserProfile,
)
from app.infra.jsonstore import JsonStore

_STORE = JsonStore({"user_profile"})


class SqliteProfileRepository:
    """Repository adapter used by profile application use cases."""

    def get_profile(self, profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
        return _STORE.load("user_profile", UserProfile, profile_id)

    def save_profile(self, profile: UserProfile) -> None:
        _STORE.save("user_profile", profile.id, profile.model_dump_json())
