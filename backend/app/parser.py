"""Compatibility facade for Garmin FIT parsing.

The parser implementation lives under
``app.domains.garmin_health.infra.fit_parser`` because FIT decoding and
timestamp semantics produce canonical Garmin health contracts.  This module
keeps older imports working for the active ingest API while avoiding new parser
logic at the app root.
"""

from app.domains.garmin_health.infra.fit_parser import (
    _GARMIN_EPOCH_UNIX,
    _extract_hrv,
    _extract_skin_temp,
    _extract_sleep,
    _extract_utc_offset_hours,
    _extract_wellness,
    _parse_day,
    _resolve_timestamp_16,
    _shift_timestamps,
    decode_fit_file,
    get_available_days,
    get_day_summary,
    get_files_by_day,
    parse_all_days,
    parse_datetime,
    parse_day,
    parse_hrv_day,
    parse_skin_temp_day,
    parse_sleep_day,
    parse_wellness_day,
)

__all__ = [
    "_GARMIN_EPOCH_UNIX",
    "_extract_hrv",
    "_extract_skin_temp",
    "_extract_sleep",
    "_extract_utc_offset_hours",
    "_extract_wellness",
    "_parse_day",
    "_resolve_timestamp_16",
    "_shift_timestamps",
    "decode_fit_file",
    "get_available_days",
    "get_day_summary",
    "get_files_by_day",
    "parse_all_days",
    "parse_datetime",
    "parse_day",
    "parse_hrv_day",
    "parse_skin_temp_day",
    "parse_sleep_day",
    "parse_wellness_day",
]
