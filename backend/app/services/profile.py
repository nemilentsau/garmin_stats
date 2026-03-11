"""Profile service."""

from ..infra.database import load_user_profile, save_user_profile
from ..models import UserProfile

_PROFILE_ID = "default"


def get_user_profile() -> UserProfile:
    """Return the stored profile or an empty default profile."""
    return load_user_profile() or UserProfile()


def update_user_profile(profile: UserProfile) -> UserProfile:
    """Persist and return the user profile."""
    normalized = profile.model_copy(update={"id": _PROFILE_ID})
    save_user_profile(normalized)
    return normalized
