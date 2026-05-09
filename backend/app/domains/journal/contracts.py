"""Contracts for user-authored journal context."""

from __future__ import annotations

from app.contracts.base import AutoTotalResponse, DefaultsRequired


class DailyCheckIn(DefaultsRequired):
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
    id: str
    date: str
    category: str
    title: str
    content: str
    tags: list[str] = []


class DailyCheckInsResponse(AutoTotalResponse, items_field="checkins"):
    checkins: list[DailyCheckIn] = []


class NotesResponse(AutoTotalResponse, items_field="notes"):
    notes: list[Note] = []
