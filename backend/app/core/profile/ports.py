"""Repository contracts for profile configuration."""

from __future__ import annotations

from typing import Protocol

from app.models import UserProfile


class ProfileRepository(Protocol):
    def get_profile(self, profile_id: str = "default") -> UserProfile | None: ...

    def save_profile(self, profile: UserProfile) -> None: ...
