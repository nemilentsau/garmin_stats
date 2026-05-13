"""SQLite-backed profile repository adapter.

Profile is core app configuration rather than a product domain, but it still
owns its persistence boundary. This adapter stores JSON-backed profile records
through the shared SQLite connection primitives without routing through a
global database module.
"""

from app.core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    Goal,
    UserProfile,
)
from app.infra.jsonstore import JsonStore

_STORE = JsonStore({"user_profile", "goals"})


def save_user_profile(profile: UserProfile) -> None:
    """Persist the app profile JSON record."""
    _STORE.save("user_profile", profile.id, profile.model_dump_json())


def load_user_profile(profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
    """Load one app profile JSON record by id."""
    return _STORE.load("user_profile", UserProfile, profile_id)


def save_goal(goal: Goal) -> None:
    """Persist one profile goal JSON record."""
    _STORE.save("goals", goal.id, goal.model_dump_json())


def load_goals() -> list[Goal]:
    """Load all profile goal records."""
    return _STORE.load_many("goals", Goal)


class SqliteProfileRepository:
    """Repository adapter used by profile application use cases."""

    def get_profile(self, profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
        return load_user_profile(profile_id=profile_id)

    def save_profile(self, profile: UserProfile) -> None:
        save_user_profile(profile)
