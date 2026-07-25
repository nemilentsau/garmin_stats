"""Coach lifecycle-time helpers.

Run and evidence dates remain local calendar values. Infrastructure instants use
canonical UTC strings so SQLite text comparisons stay chronological across DST.
"""

from datetime import UTC, date, datetime, time


def utc_now_iso() -> str:
    """Return the current UTC instant with fixed-width microseconds and ``Z``."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def local_today_iso() -> str:
    """Local calendar day used for Coach evidence dates."""
    return datetime.now().astimezone().date().isoformat()


def utc_cutoff_iso(value: str | None) -> str | None:
    """Normalize an exclusive cutoff to fixed-width canonical UTC."""
    if value is None:
        return None
    if len(value) == 10:
        instant = datetime.combine(date.fromisoformat(value), time.min).astimezone()
    else:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.astimezone()
    return (
        instant.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
