"""Contracts for profile configuration."""

from __future__ import annotations

from app.contracts.base import DefaultsRequired

DEFAULT_PROFILE_ID = "default"


class UserProfile(DefaultsRequired):
    id: str = DEFAULT_PROFILE_ID
    name: str | None = None
    birth_year: int | None = None
    age_range: str | None = None
    sex: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    primary_goals: list[str] = []
    constraints: list[str] = []
    injuries: list[str] = []
    equipment: list[str] = []
    default_weekly_schedule: list[str] = []
    sleep_constraints: list[str] = []
    nutrition_preferences: list[str] = []
    coaching_style_preferences: list[str] = []
