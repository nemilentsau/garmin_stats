"""Infrastructure API response contracts."""

from __future__ import annotations

from app.contracts.base import AutoTotalResponse, DefaultsRequired


class DaySummaryResponse(DefaultsRequired):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(AutoTotalResponse, items_field="days"):
    days: list[str]
    total: int = 0
