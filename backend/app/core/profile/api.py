"""Profile HTTP routes."""

from fastapi import APIRouter

from app.bootstrap.container import build_container
from app.core.profile.application import get_user_profile, update_user_profile
from app.models import UserProfile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=UserProfile)
def get_profile():
    """Return the current user profile."""
    return get_user_profile(build_container().profile_repo)


@router.put("", response_model=UserProfile)
def put_profile(profile: UserProfile):
    """Create or replace the user profile."""
    return update_user_profile(build_container().profile_repo, profile)
