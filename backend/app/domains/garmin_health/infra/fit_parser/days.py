"""Day-level FIT parser composition for Garmin health contracts.

This module owns cross-file merging, day assembly, and local-time normalization
for parsed Garmin health data.  It is called by Garmin sync ingestion, while
archive acquisition and persistence remain outside this package.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from app.domains.garmin_health.contracts import (
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
)
from app.domains.garmin_health.infra.fit_parser.decode import decode_fit_file
from app.domains.garmin_health.infra.fit_parser.extractors import (
    _extract_hrv,
    _extract_skin_temp,
    _extract_sleep,
    _extract_wellness,
)
from app.domains.garmin_health.infra.fit_parser.files import get_files_by_day
from app.domains.garmin_health.infra.fit_parser.timestamps import (
    _extract_offset_from_files,
    _shift_timestamps,
)

log = logging.getLogger(__name__)


def _parse_day[ParsedDay: (DayWellness, DaySleep, DayHrv, DaySkinTemp)](
    files: list[Path],
    date: str,
    *,
    empty: Callable[..., ParsedDay],
    extractor: Callable[[dict, str], ParsedDay],
    list_fields: tuple[str, ...],
) -> ParsedDay:
    """Decode one metric type's files for a day and merge configured list fields."""
    merged = empty(date=date)
    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            extracted = extractor(messages, date)
            for field in list_fields:
                getattr(merged, field).extend(getattr(extracted, field))
        except Exception as e:
            log.warning("Error parsing %s: %s", fit_file, e)
    return merged


def parse_wellness_day(files: list[Path], date: str) -> DayWellness:
    """Decode all WELLNESS files for one day, merge into a single DayWellness."""
    return _parse_day(
        files,
        date,
        empty=DayWellness,
        extractor=_extract_wellness,
        list_fields=(
            "heart_rate",
            "stress",
            "body_battery",
            "spo2",
            "respiration",
            "activity",
            "steps_summary",
            "resting_hr",
        ),
    )


def parse_sleep_day(files: list[Path], date: str) -> DaySleep:
    """Decode all SLEEP_DATA files for one day, merge."""
    return _parse_day(
        files,
        date,
        empty=DaySleep,
        extractor=_extract_sleep,
        list_fields=("sleep_levels", "sleep_assessments"),
    )


def parse_hrv_day(files: list[Path], date: str) -> DayHrv:
    """Decode all HRV_STATUS files for one day, merge."""
    return _parse_day(
        files,
        date,
        empty=DayHrv,
        extractor=_extract_hrv,
        list_fields=("hrv_values", "hrv_summaries"),
    )


def parse_skin_temp_day(files: list[Path], date: str) -> DaySkinTemp:
    """Decode all SKIN_TEMP files for one day, merge."""
    return _parse_day(
        files,
        date,
        empty=DaySkinTemp,
        extractor=_extract_skin_temp,
        list_fields=("skin_temp_overnight",),
    )


def parse_day(date_str: str, day_files: dict[str, list[Path]]) -> DayData:
    """Parse a single day's FIT files into a DayData."""
    wellness_files = day_files.get("WELLNESS", [])
    offset = _extract_offset_from_files(wellness_files, decode_fit_file)
    day = DayData(
        date=date_str,
        utc_offset_hours=offset,
        wellness=parse_wellness_day(wellness_files, date_str),
        sleep=parse_sleep_day(day_files.get("SLEEP_DATA", []), date_str),
        hrv=parse_hrv_day(day_files.get("HRV_STATUS", []), date_str),
        skin_temp=parse_skin_temp_day(day_files.get("SKIN_TEMP", []), date_str),
    )
    if offset is not None:
        _shift_timestamps(day, offset)
    return day


def parse_all_days(data_dir: Path) -> list[DayData]:
    """Parse all metric types for all days in one directory scan."""
    files_by_day = get_files_by_day(data_dir)
    return [parse_day(d, f) for d, f in sorted(files_by_day.items())]
