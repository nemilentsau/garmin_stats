"""Timestamp coverage helpers for Garmin analytics quality summaries."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.utils.timeutil import parse_iso as _parse_iso


@dataclass(frozen=True, slots=True)
class TimestampCoverageSummary:
    """Count and time span covered by a set of optional timestamps."""

    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


def summarize_timestamp_coverage(
    timestamps: Sequence[str | None],
) -> TimestampCoverageSummary:
    """Summarize timestamp coverage while counting all source records."""
    parsed_times = sorted(
        parsed for timestamp in timestamps if (parsed := _parse_iso(timestamp)) is not None
    )
    coverage_start = parsed_times[0].isoformat() if parsed_times else None
    coverage_end = parsed_times[-1].isoformat() if parsed_times else None
    coverage_hours = (
        round((parsed_times[-1] - parsed_times[0]).total_seconds() / 3600, 2)
        if len(parsed_times) >= 2
        else None
    )
    return TimestampCoverageSummary(
        sample_count=len(timestamps),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        coverage_hours=coverage_hours,
    )
