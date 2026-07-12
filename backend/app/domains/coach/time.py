"""Coach lifecycle-time helpers.

Run and evidence dates remain local calendar values. Infrastructure instants use
canonical UTC strings so SQLite text comparisons stay chronological across DST.
"""

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return the current UTC instant with a stable ``Z`` suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
