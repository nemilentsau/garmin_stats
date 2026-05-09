"""Reusable analytical time-window helpers."""

from collections.abc import Callable
from datetime import date as date_type
from datetime import timedelta
from typing import Protocol

WINDOW_DAYS: dict[str, int | None] = {"3M": 91, "6M": 182, "All": None}


class _HasDate(Protocol):
    @property
    def date(self) -> str: ...


def compute_windows[T: _HasDate, R](
    items: list[T],
    fn: Callable[[list[T]], R],
) -> dict[str, R]:
    """Apply a calculation to each standard analytics window."""
    today = date_type.today()
    windows: dict[str, R] = {}
    for label, days in WINDOW_DAYS.items():
        if days is None:
            subset = items
        else:
            cutoff = (today - timedelta(days=days)).isoformat()
            subset = [item for item in items if item.date >= cutoff]
        windows[label] = fn(subset)
    return windows
