"""Timestamp normalization helpers for Garmin FIT parser contracts.

FIT messages mix full UTC timestamps, Garmin-epoch integers, and compressed
``timestamp_16`` values.  This module owns conversion and local-time shifting so
parser extractors can stay focused on metric-specific fields.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domains.garmin_health.contracts import DayData
from app.utils.timeutil import parse_iso

_GARMIN_EPOCH = datetime(1989, 12, 31, tzinfo=UTC)
_GARMIN_EPOCH_UNIX = int(_GARMIN_EPOCH.timestamp())

# DayData attribute -> list-field names that hold timestamped readings.
# Anything added to the canonical DayData with a `.timestamp` field must be
# registered here so it is shifted to local time at ingest.
_TIMESTAMPED_READING_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "wellness",
        (
            "heart_rate",
            "stress",
            "body_battery",
            "spo2",
            "respiration",
            "activity",
            "steps_summary",
            "resting_hr",
        ),
    ),
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


def _extract_utc_offset_hours(messages: dict) -> float | None:
    """Extract local UTC offset from WELLNESS monitoring info messages."""
    for msg in messages.get("monitoring_info_mesgs", []):
        utc_ts = msg.get("timestamp")
        local_raw = msg.get("local_timestamp")
        if utc_ts is None or local_raw is None:
            continue
        if not hasattr(utc_ts, "timestamp"):
            continue
        local_dt = datetime.fromtimestamp(int(local_raw) + _GARMIN_EPOCH_UNIX, tz=UTC)
        return (local_dt - utc_ts).total_seconds() / 3600
    return None


def _shift_iso(iso: str | None, delta: timedelta) -> str | None:
    if iso is None:
        return None
    dt = parse_iso(iso)
    if dt is None:
        return iso
    return (dt + delta).replace(tzinfo=None).isoformat()


def _shift_timestamps(day: DayData, offset_hours: float) -> None:
    """Shift all timestamp fields in a DayData from UTC to local time."""
    delta = timedelta(hours=offset_hours)
    for group_name, list_fields in _TIMESTAMPED_READING_FIELDS:
        group = getattr(day, group_name)
        for field in list_fields:
            for reading in getattr(group, field):
                reading.timestamp = _shift_iso(reading.timestamp, delta)
