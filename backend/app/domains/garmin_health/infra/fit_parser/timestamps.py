"""Timestamp normalization helpers for Garmin FIT parser contracts.

FIT messages mix full UTC timestamps, Garmin-epoch integers, and compressed
``timestamp_16`` values.  This module owns conversion and local-time shifting so
parser extractors can stay focused on metric-specific fields.
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domains.garmin_health.contracts import DayData, DayWellness
from app.utils.timeutil import parse_iso

_GARMIN_EPOCH = datetime(1989, 12, 31, tzinfo=UTC)
_GARMIN_EPOCH_UNIX = int(_GARMIN_EPOCH.timestamp())

# Anything added to the canonical DayData with a `.timestamp` field must be
# registered in one of the two tuples below so it is shifted to local time at
# ingest.  They are split because WELLNESS files carry their own offsets and are
# shifted per source file, while the overnight files carry none and ride the
# day-wide timeline.
_WELLNESS_TIMESTAMPED_FIELDS: tuple[str, ...] = (
    "heart_rate",
    "stress",
    "body_battery",
    "spo2",
    "respiration",
    "activity",
    "steps_summary",
    "resting_hr",
)
# DayData attribute -> list-field names holding timestamped overnight readings.
_OVERNIGHT_TIMESTAMPED_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sleep", ("sleep_levels",)),
    ("hrv", ("hrv_values",)),
    ("skin_temp", ("skin_temp_overnight",)),
)


def parse_datetime(dt: Any) -> str | None:
    """Convert a decoded FIT datetime-like value to an ISO string."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _resolve_timestamp_16(ts16: int, ref_garmin: int) -> datetime:
    """Resolve a compressed 16-bit FIT timestamp using a reference timestamp."""
    upper = ref_garmin & ~0xFFFF
    resolved = upper | ts16
    if resolved < ref_garmin:
        resolved += 0x10000
    return datetime.fromtimestamp(resolved + _GARMIN_EPOCH_UNIX, tz=UTC)


Breakpoint = tuple[datetime, float]


class UtcOffsetTimeline:
    """The UTC offsets in effect over time, newest change last.

    Garmin writes a ``monitoring_info`` message whenever the watch's local
    offset changes, so one calendar day can carry several offsets: a DST
    rollover or a flight moves the wearer mid-day, sometimes inside a single
    WELLNESS file.  Resolving each reading against its own instant keeps every
    stored timestamp true local time; a day whose files all agree resolves to
    that single offset everywhere.
    """

    def __init__(self, breakpoints: Iterable[Breakpoint]) -> None:
        # Stable sort on the instant alone: same-instant markers keep the order
        # their files were read in, so resolution is deterministic.
        self._breakpoints: list[Breakpoint] = sorted(breakpoints, key=lambda bp: bp[0])

    def __bool__(self) -> bool:
        return bool(self._breakpoints)

    @property
    def final_offset(self) -> float | None:
        """The offset in effect at the end of the covered span.

        ``DayData.utc_offset_hours`` carries this one: a day that changes offset
        is labelled with the zone its wearer ended it in, matching how the day's
        latest readings display.
        """
        return self._breakpoints[-1][1] if self._breakpoints else None

    def offset_at(self, moment: datetime) -> float | None:
        """The offset in effect at a UTC instant.

        Readings that precede the first marker (a file can start before its own
        ``monitoring_info``) take the earliest known offset.
        """
        if not self._breakpoints:
            return None
        offset = self._breakpoints[0][1]
        for start, value in self._breakpoints:
            if start > moment:
                break
            offset = value
        return offset


def _extract_utc_offset_breakpoints(messages: dict) -> list[Breakpoint]:
    """Every UTC-offset marker in one decoded WELLNESS file, in message order."""
    breakpoints: list[Breakpoint] = []
    for msg in messages.get("monitoring_info_mesgs", []):
        utc_ts = msg.get("timestamp")
        local_raw = msg.get("local_timestamp")
        if utc_ts is None or local_raw is None:
            continue
        if not hasattr(utc_ts, "timestamp"):
            continue
        local_dt = datetime.fromtimestamp(int(local_raw) + _GARMIN_EPOCH_UNIX, tz=UTC)
        breakpoints.append((utc_ts, (local_dt - utc_ts).total_seconds() / 3600))
    return breakpoints


def _shift_iso(iso: str | None, timeline: UtcOffsetTimeline) -> str | None:
    if iso is None:
        return None
    dt = parse_iso(iso)
    if dt is None:
        return iso
    moment = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    offset = timeline.offset_at(moment)
    if offset is None:
        return iso
    return (dt + timedelta(hours=offset)).replace(tzinfo=None).isoformat()


def _shift_readings(group: Any, list_fields: tuple[str, ...], timeline: UtcOffsetTimeline) -> None:
    for field in list_fields:
        for reading in getattr(group, field):
            reading.timestamp = _shift_iso(reading.timestamp, timeline)


def _shift_wellness_to_local(wellness: DayWellness, timeline: UtcOffsetTimeline) -> None:
    """Shift one WELLNESS file's readings from UTC to local time."""
    if not timeline:
        return
    _shift_readings(wellness, _WELLNESS_TIMESTAMPED_FIELDS, timeline)


def _shift_overnight_to_local(day: DayData, timeline: UtcOffsetTimeline) -> None:
    """Shift sleep, HRV, and skin-temp readings from UTC to local time.

    Those files carry no ``monitoring_info`` of their own, so they ride the
    day-wide timeline built from the day's WELLNESS files.  Wellness is skipped
    here: it is already shifted per source file during the wellness parse.
    """
    if not timeline:
        return
    for group_name, list_fields in _OVERNIGHT_TIMESTAMPED_FIELDS:
        _shift_readings(getattr(day, group_name), list_fields, timeline)
