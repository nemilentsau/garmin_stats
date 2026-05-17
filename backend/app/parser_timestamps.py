"""Timestamp normalization helpers for Garmin FIT parser contracts.

FIT messages mix full UTC timestamps, Garmin-epoch integers, and compressed
``timestamp_16`` values.  This module owns conversion and local-time shifting so
parser extractors can stay focused on metric-specific fields.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.domains.garmin_health.contracts import DayData

# Garmin FIT epoch: Dec 31, 1989 00:00:00 UTC
_GARMIN_EPOCH = datetime(1989, 12, 31, tzinfo=UTC)
_GARMIN_EPOCH_UNIX = int(_GARMIN_EPOCH.timestamp())


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


def _extract_offset_from_files(
    files: list[Path],
    decode_fit_file: Callable[[Path], dict[str, list[dict]]],
) -> float | None:
    """Decode WELLNESS files until one yields a UTC offset."""
    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            offset = _extract_utc_offset_hours(messages)
            if offset is not None:
                return offset
        except Exception:
            continue
    return None


def _shift_timestamps(day: DayData, offset_hours: float) -> None:
    """Shift all timestamp fields in a DayData from UTC to local time."""
    delta = timedelta(hours=offset_hours)

    def shift(iso: str | None) -> str | None:
        if iso is None:
            return None
        try:
            dt = datetime.fromisoformat(iso) + delta
            return dt.replace(tzinfo=None).isoformat()
        except (ValueError, TypeError):
            return iso

    for r in day.wellness.heart_rate:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.stress:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.body_battery:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.spo2:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.respiration:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.activity:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.steps_summary:
        r.timestamp = shift(r.timestamp)
    for r in day.wellness.resting_hr:
        r.timestamp = shift(r.timestamp)

    for r in day.sleep.sleep_levels:
        r.timestamp = shift(r.timestamp)

    for r in day.hrv.hrv_values:
        r.timestamp = shift(r.timestamp)

    for r in day.skin_temp.skin_temp_overnight:
        r.timestamp = shift(r.timestamp)
