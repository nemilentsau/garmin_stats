"""Profile configuration use cases."""

from app.models import DEFAULT_PROFILE_ID, UserProfile

from .ports import ProfileRepository


def get_user_profile(repo: ProfileRepository) -> UserProfile:
    """Return the stored profile or an empty default profile."""
    return repo.get_profile() or UserProfile()


def update_user_profile(repo: ProfileRepository, profile: UserProfile) -> UserProfile:
    """Persist and return the user profile."""
    normalized = profile.model_copy(update={"id": DEFAULT_PROFILE_ID})
    repo.save_profile(normalized)
    return normalized
