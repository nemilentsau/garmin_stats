"""Shared timestamp utilities."""

from datetime import UTC, datetime, timedelta
from datetime import date as date_type


def date_range(start: str, end: str) -> list[str]:
    """Return all ISO date strings from ``start`` to ``end`` inclusive.

    The one inclusive local-date range generator, shared by analytics trend densification and
    experiment window math. Local dates only — the parser already shifts Garmin timestamps to
    local time, so callers pass plain ISO dates.
    """
    start_day = date_type.fromisoformat(start)
    end_day = date_type.fromisoformat(end)
    return [
        (start_day + timedelta(days=n)).isoformat()
        for n in range((end_day - start_day).days + 1)
    ]


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string, returning None on failure."""
    if not ts:
        return None
    normalized = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
