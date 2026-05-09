"""Repository contracts for profile configuration."""

from __future__ import annotations

from typing import Protocol

from app.core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    UserProfile,
)


class ProfileRepository(Protocol):
    def get_profile(self, profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None: ...

    def save_profile(self, profile: UserProfile) -> None: ...
