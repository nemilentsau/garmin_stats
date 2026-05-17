"""
Garmin FIT file parser — three layers:

  Layer 1: Per-file extractors (_extract_*)
  Layer 2: Per-day parsers (parse_*_day) — merge multiple files of same type
  Layer 3: High-level functions (parse_*) — directory scan + date filter

All timestamps are converted from UTC to local time at ingest.
The UTC offset is extracted from monitoring_info_mesgs (timestamp vs
local_timestamp) and applied via _shift_timestamps().  When adding new
timestamp fields, add them to _shift_timestamps() so they are also
converted to local time.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from garmin_fit_sdk import Decoder, Stream

from app.domains.garmin_health.contracts import (
    ActivityReading,
    BodyBatteryReading,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvSummary,
    HrvValue,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SleepLevel,
    SpO2Reading,
    StepsReading,
    StressReading,
)
from app.parser_files import get_available_days, get_day_summary, get_files_by_day
from app.parser_timestamps import (
    _GARMIN_EPOCH_UNIX,
    _extract_offset_from_files,
    _extract_utc_offset_hours,
    _resolve_timestamp_16,
    _shift_timestamps,
    parse_datetime,
)

log = logging.getLogger(__name__)

__all__ = [
    "_GARMIN_EPOCH_UNIX",
    "_extract_hrv",
    "_extract_offset_from_files",
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
    "parse_hrv",
    "parse_hrv_day",
    "parse_skin_temp",
    "parse_skin_temp_day",
    "parse_sleep",
    "parse_sleep_day",
    "parse_wellness",
    "parse_wellness_day",
]


# ---------------------------------------------------------------------------
# FIT decoding
# ---------------------------------------------------------------------------

def decode_fit_file(file_path: Path) -> dict[str, list[dict]]:
    """Decode a FIT file and return messages as dict."""
    stream = Stream.from_file(str(file_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read()
    return messages


# ---------------------------------------------------------------------------
# Layer 1 — Per-file extractors
# ---------------------------------------------------------------------------

def _extract_wellness(messages: dict, date: str) -> DayWellness:
    """Extract all wellness readings from a single decoded WELLNESS file."""
    hr: list[HeartRateReading] = []
    stress: list[StressReading] = []
    body_battery: list[BodyBatteryReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []

    # Track reference timestamp for resolving compressed timestamp_16 values.
    # FIT monitoring files interleave full-timestamp messages with compressed
    # ones; we update the reference whenever a full timestamp appears.
    ref_garmin: int | None = None

    # Single pass over monitoring_mesgs (fixes triple-iteration)
    for msg in messages.get("monitoring_mesgs", []):
        full_ts = msg.get("timestamp")
        if full_ts is not None and hasattr(full_ts, "timestamp"):
            ref_garmin = int(full_ts.timestamp()) - _GARMIN_EPOCH_UNIX

        # Resolve timestamp: prefer full, fall back to compressed timestamp_16
        ts16 = msg.get("timestamp_16")
        if full_ts is not None:
            ts = parse_datetime(full_ts)
        elif ts16 is not None and ref_garmin is not None:
            resolved = _resolve_timestamp_16(ts16, ref_garmin)
            ts = resolved.isoformat()
            ref_garmin = int(resolved.timestamp()) - _GARMIN_EPOCH_UNIX
        else:
            ts = None

        hr_value = msg.get("heart_rate")
        if hr_value is not None and hr_value > 0:
            hr.append(HeartRateReading(timestamp=ts, value=hr_value))

        if "activity_type" in msg:
            activity.append(ActivityReading(
                timestamp=ts,
                activity_type=str(msg.get("activity_type", "unknown")),
                intensity=msg.get("intensity"),
                steps=msg.get("steps"),
                calories=msg.get("active_calories"),
                distance=msg.get("distance"),
            ))

        steps_value = msg.get("steps")
        if steps_value is not None:
            steps.append(StepsReading(
                timestamp=ts,
                steps=steps_value,
                distance=msg.get("distance"),
                calories=msg.get("active_calories"),
            ))

    for msg in messages.get("stress_level_mesgs", []):
        ts = parse_datetime(msg.get("stress_level_time"))
        value = msg.get("stress_level_value")
        if value is not None and value >= 0:
            stress.append(StressReading(timestamp=ts, value=value))
        bb_value = msg.get(3)
        if bb_value is not None and ts is not None:
            body_battery.append(BodyBatteryReading(timestamp=ts, value=bb_value))

    for msg in messages.get("spo2_data_mesgs", []):
        ts = parse_datetime(msg.get("timestamp"))
        value = msg.get("reading_spo2")
        confidence = msg.get("reading_confidence")
        if value is not None:
            spo2.append(SpO2Reading(
                timestamp=ts,
                value=value,
                confidence=confidence,
                mode=str(msg.get("mode", "unknown")),
            ))

    for msg in messages.get("respiration_rate_mesgs", []):
        ts = parse_datetime(msg.get("timestamp"))
        value = msg.get("respiration_rate")
        if value is not None and value > 0:
            respiration.append(RespirationReading(timestamp=ts, value=value))

    for msg in messages.get("monitoring_hr_data_mesgs", []):
        ts = parse_datetime(msg.get("timestamp"))
        resting_hr.append(RestingHRReading(
            timestamp=ts,
            resting_hr=msg.get("resting_heart_rate"),
            current_day_resting_hr=msg.get("current_day_resting_heart_rate"),
        ))

    return DayWellness(
        date=date,
        heart_rate=hr,
        stress=stress,
        body_battery=body_battery,
        spo2=spo2,
        respiration=respiration,
        activity=activity,
        steps_summary=steps,
        resting_hr=resting_hr,
    )


def _extract_sleep(messages: dict, date: str) -> DaySleep:
    """Extract sleep data from a single decoded SLEEP_DATA file."""
    levels: list[SleepLevel] = []
    assessments: list[SleepAssessment] = []

    for msg in messages.get("sleep_level_mesgs", []):
        ts = parse_datetime(msg.get("timestamp"))
        levels.append(SleepLevel(
            date=date,
            timestamp=ts,
            level=str(msg.get("sleep_level", "unknown")),
        ))

    for msg in messages.get("sleep_assessment_mesgs", []):
        assessments.append(SleepAssessment(
            date=date,
            overall_score=msg.get("overall_sleep_score"),
            deep_sleep_score=msg.get("deep_sleep_score"),
            light_sleep_score=msg.get("light_sleep_score"),
            rem_sleep_score=msg.get("rem_sleep_score"),
            awake_time_score=msg.get("awake_time_score"),
            awakenings_count=msg.get("awakenings_count"),
            average_stress=msg.get("average_stress_during_sleep"),
        ))

    return DaySleep(date=date, sleep_levels=levels, sleep_assessments=assessments)


def _extract_hrv(messages: dict, date: str) -> DayHrv:
    """Extract HRV data from a single decoded HRV_STATUS file."""
    values: list[HrvValue] = []
    summaries: list[HrvSummary] = []

    for msg in messages.get("hrv_value_mesgs", []):
        ts = parse_datetime(msg.get("timestamp"))
        value = msg.get("value")
        if value is not None:
            values.append(HrvValue(date=date, timestamp=ts, value=value))

    for msg in messages.get("hrv_status_summary_mesgs", []):
        summaries.append(HrvSummary(
            date=date,
            weekly_average=msg.get("weekly_average"),
            last_night_average=msg.get("last_night_average"),
            last_night_5_min_high=msg.get("last_night_5_min_high"),
            baseline_low_upper=msg.get("baseline_low_upper"),
            baseline_balanced_lower=msg.get("baseline_balanced_lower"),
            baseline_balanced_upper=msg.get("baseline_balanced_upper"),
            status=str(msg.get("status", "unknown")),
        ))

    return DayHrv(date=date, hrv_values=values, hrv_summaries=summaries)


def _extract_skin_temp(messages: dict, date: str) -> DaySkinTemp:
    """Extract skin temp data from a single decoded SKIN_TEMP file."""
    readings: list[SkinTempOvernight] = []

    for msg in messages.get("skin_temp_overnight_mesgs", []):
        readings.append(SkinTempOvernight(
            date=date,
            timestamp=parse_datetime(msg.get("timestamp")),
            local_timestamp=msg.get("local_timestamp"),
            nightly_value=msg.get("nightly_value"),
            average_deviation=msg.get("average_deviation"),
            average_7_day_deviation=msg.get("average_7_day_deviation"),
        ))

    return DaySkinTemp(date=date, skin_temp_overnight=readings)


# ---------------------------------------------------------------------------
# Layer 2 — Per-day parsers (merge multiple files of same type)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Layer 3 — High-level functions (directory scan + date filter)
# ---------------------------------------------------------------------------

def _select_days(
    files_by_day: dict[str, dict[str, list[Path]]],
    date: str | None,
) -> list[tuple[str, dict[str, list[Path]]]]:
    """Select and sort days to process. Returns list of (date, files_dict) tuples."""
    if date:
        if date not in files_by_day:
            return []
        return [(date, files_by_day[date])]
    return sorted(files_by_day.items())


def parse_wellness(data_dir: Path, date: str | None = None) -> list[DayWellness]:
    """Parse wellness data across days."""
    days = _select_days(get_files_by_day(data_dir), date)
    return [
        parse_wellness_day(day_files.get("WELLNESS", []), d)
        for d, day_files in days
    ]


def parse_sleep(data_dir: Path, date: str | None = None) -> list[DaySleep]:
    """Parse sleep data across days."""
    days = _select_days(get_files_by_day(data_dir), date)
    return [
        parse_sleep_day(day_files.get("SLEEP_DATA", []), d)
        for d, day_files in days
    ]


def parse_hrv(data_dir: Path, date: str | None = None) -> list[DayHrv]:
    """Parse HRV data across days."""
    days = _select_days(get_files_by_day(data_dir), date)
    return [
        parse_hrv_day(day_files.get("HRV_STATUS", []), d)
        for d, day_files in days
    ]


def parse_skin_temp(data_dir: Path, date: str | None = None) -> list[DaySkinTemp]:
    """Parse skin temp data across days."""
    days = _select_days(get_files_by_day(data_dir), date)
    return [
        parse_skin_temp_day(day_files.get("SKIN_TEMP", []), d)
        for d, day_files in days
    ]


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
    """Parse all metric types for all days — single directory scan."""
    files_by_day = get_files_by_day(data_dir)
    return [parse_day(d, f) for d, f in sorted(files_by_day.items())]
