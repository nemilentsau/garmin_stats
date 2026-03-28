"""Profile HTTP routes."""

from fastapi import APIRouter

from ..models import UserProfile
from ..services.profile import get_user_profile, update_user_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=UserProfile)
def get_profile():
    """Return the current user profile."""
    return get_user_profile()


@router.put("", response_model=UserProfile)
def put_profile(profile: UserProfile):
    """Create or replace the user profile."""
    return update_user_profile(profile)
