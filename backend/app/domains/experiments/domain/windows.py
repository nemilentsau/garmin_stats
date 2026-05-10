"""Date-window helpers for experiment domain calculations.

Experiment windows are inclusive local-date ranges. The parser already shifts
Garmin timestamps to local time, so these helpers only operate on ISO dates.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta


def date_range(start: str, end: str) -> list[str]:
    """Return all ISO date strings from ``start`` to ``end`` inclusive."""
    day = date_type.fromisoformat(start)
    end_day = date_type.fromisoformat(end)
    days: list[str] = []
    while day <= end_day:
        days.append(day.isoformat())
        day += timedelta(days=1)
    return days
