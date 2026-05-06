"""Pure planning helpers for Garmin archive sync."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SyncDatePlan:
    deleted_latest: date | None
    dates: list[date]
    initial_affected_dates: list[str]


def plan_sync_dates(*, latest: date | None, today: date) -> SyncDatePlan:
    """Return the dates the sync workflow should inspect and refresh."""
    if latest is None:
        start_date = today - timedelta(days=1)
        deleted_latest = None
        initial_affected_dates: list[str] = []
    else:
        start_date = latest
        deleted_latest = latest
        initial_affected_dates = [latest.isoformat()]

    dates: list[date] = []
    current = start_date
    while current <= today:
        dates.append(current)
        current += timedelta(days=1)

    return SyncDatePlan(
        deleted_latest=deleted_latest,
        dates=dates,
        initial_affected_dates=initial_affected_dates,
    )
