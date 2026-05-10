"""Pydantic contracts owned by the journal domain.

These models describe user-authored daily context: subjective check-ins and
freeform dated notes. Consumers may read them as context, but this domain owns
their request and response shapes.
"""

from __future__ import annotations

from app.contracts.base import AutoTotalResponse, DefaultsRequired


class DailyCheckIn(DefaultsRequired):
    """Subjective daily state captured once per local date."""

    id: str
    date: str
    energy: int | None = None
    mood: int | None = None
    motivation: int | None = None
    soreness: int | None = None
    stress_subjective: int | None = None
    sleep_quality_subjective: int | None = None
    workload_subjective: int | None = None
    illness_flag: bool = False
    travel_flag: bool = False
    alcohol_flag: bool = False
    notes: str | None = None


class Note(DefaultsRequired):
    """Freeform user note attached to a local date."""

    id: str
    date: str
    category: str
    title: str
    content: str
    tags: list[str] = []


class DailyCheckInsResponse(AutoTotalResponse, items_field="checkins"):
    """List response for dated daily check-ins."""

    checkins: list[DailyCheckIn] = []


class NotesResponse(AutoTotalResponse, items_field="notes"):
    """List response for dated journal notes."""

    notes: list[Note] = []
