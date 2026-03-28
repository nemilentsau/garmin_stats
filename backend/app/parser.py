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
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from garmin_fit_sdk import Decoder, Stream

from .models import (
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

log = logging.getLogger(__name__)

# Garmin FIT epoch: Dec 31, 1989 00:00:00 UTC
_GARMIN_EPOCH = datetime(1989, 12, 31, tzinfo=UTC)
_GARMIN_EPOCH_UNIX = int(_GARMIN_EPOCH.timestamp())


# ---------------------------------------------------------------------------
# Utilities (unchanged)
# ---------------------------------------------------------------------------

def decode_fit_file(file_path: Path) -> dict[str, list[dict]]:
    """Decode a FIT file and return messages as dict."""
    stream = Stream.from_file(str(file_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read()
    return messages


def parse_datetime(dt: Any) -> str | None:
    """Convert datetime to ISO string."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _resolve_timestamp_16(ts16: int, ref_garmin: int) -> datetime:
    """Resolve a compressed 16-bit FIT timestamp using a reference timestamp.

    FIT monitoring messages use ``timestamp_16`` — the lower 16 bits of a
    full Garmin-epoch timestamp.  We reconstruct the full timestamp by
    combining these with the upper bits of the most recent reference
    timestamp, handling 16-bit rollover.
    """
    upper = ref_garmin & ~0xFFFF
    resolved = upper | ts16
    if resolved < ref_garmin:
        resolved += 0x10000  # 16-bit rollover
    return datetime.fromtimestamp(resolved + _GARMIN_EPOCH_UNIX, tz=UTC)


def _is_canonical_day_dir_name(name: str) -> bool:
    """Return True only for exact YYYY-MM-DD day directory names."""
    if len(name) != 10:
        return False
    try:
        return date_cls.fromisoformat(name).isoformat() == name
    except ValueError:
        return False


def get_available_days(data_dir: Path) -> list[str]:
    """Get list of available date directories."""
    if not data_dir.exists():
        return []
    return sorted([
        d.name
        for d in data_dir.iterdir()
        if d.is_dir() and _is_canonical_day_dir_name(d.name)
    ])


def get_files_by_day(data_dir: Path) -> dict[str, dict[str, list[Path]]]:
    """Group FIT files by date and type."""
    files_by_day: dict[str, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))

    for fit_file in data_dir.rglob("*.fit"):
        rel_parts = fit_file.relative_to(data_dir).parts
        if not rel_parts:
            continue
        date_dir = rel_parts[0]
        if not _is_canonical_day_dir_name(date_dir):
            continue
        name_parts = fit_file.stem.split("_")
        file_type = "_".join(name_parts[1:]) if len(name_parts) >= 2 else "UNKNOWN"
        files_by_day[date_dir][file_type].append(fit_file)

    return {k: dict(v) for k, v in sorted(files_by_day.items())}


def get_day_summary(data_dir: Path, date: str) -> dict:
    """Get summary for a specific day."""
    day_dir = data_dir / date
    if not day_dir.exists():
        return {"error": f"Day {date} not found"}

    files = list(day_dir.glob("*.fit"))
    file_types: dict[str, int] = defaultdict(int)

    for f in files:
        name_parts = f.stem.split("_")
        file_type = "_".join(name_parts[1:]) if len(name_parts) >= 2 else "UNKNOWN"
        file_types[file_type] += 1

    return {
        "date": date,
        "total_files": len(files),
        "file_types": dict(file_types),
        "total_size_kb": round(sum(f.stat().st_size for f in files) / 1024, 1),
    }


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
# UTC offset extraction + timestamp shifting
# ---------------------------------------------------------------------------

def _extract_utc_offset_hours(messages: dict) -> float | None:
    """Extract UTC offset from monitoring_info_mesgs.

    Each WELLNESS file carries monitoring_info with both a UTC `timestamp`
    and a `local_timestamp` (Garmin-epoch int).  The difference gives the
    device's local UTC offset for that day.
    """
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


def _extract_offset_from_files(files: list[Path]) -> float | None:
    """Decode WELLNESS files until we find a UTC offset, then return it."""
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

    # Wellness readings
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

    # Sleep
    for r in day.sleep.sleep_levels:
        r.timestamp = shift(r.timestamp)

    # HRV
    for r in day.hrv.hrv_values:
        r.timestamp = shift(r.timestamp)

    # Skin temp
    for r in day.skin_temp.skin_temp_overnight:
        r.timestamp = shift(r.timestamp)


# ---------------------------------------------------------------------------
# Layer 2 — Per-day parsers (merge multiple files of same type)
# ---------------------------------------------------------------------------

def parse_wellness_day(files: list[Path], date: str) -> DayWellness:
    """Decode all WELLNESS files for one day, merge into a single DayWellness."""
    merged = DayWellness(date=date)
    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            extracted = _extract_wellness(messages, date)
            merged.heart_rate.extend(extracted.heart_rate)
            merged.stress.extend(extracted.stress)
            merged.body_battery.extend(extracted.body_battery)
            merged.spo2.extend(extracted.spo2)
            merged.respiration.extend(extracted.respiration)
            merged.activity.extend(extracted.activity)
            merged.steps_summary.extend(extracted.steps_summary)
            merged.resting_hr.extend(extracted.resting_hr)
        except Exception as e:
            log.warning("Error parsing %s: %s", fit_file, e)
    return merged


def parse_sleep_day(files: list[Path], date: str) -> DaySleep:
    """Decode all SLEEP_DATA files for one day, merge."""
    merged = DaySleep(date=date)
    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            extracted = _extract_sleep(messages, date)
            merged.sleep_levels.extend(extracted.sleep_levels)
            merged.sleep_assessments.extend(extracted.sleep_assessments)
        except Exception as e:
            log.warning("Error parsing %s: %s", fit_file, e)
    return merged


def parse_hrv_day(files: list[Path], date: str) -> DayHrv:
    """Decode all HRV_STATUS files for one day, merge."""
    merged = DayHrv(date=date)
    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            extracted = _extract_hrv(messages, date)
            merged.hrv_values.extend(extracted.hrv_values)
            merged.hrv_summaries.extend(extracted.hrv_summaries)
        except Exception as e:
            log.warning("Error parsing %s: %s", fit_file, e)
    return merged


def parse_skin_temp_day(files: list[Path], date: str) -> DaySkinTemp:
    """Decode all SKIN_TEMP files for one day, merge."""
    merged = DaySkinTemp(date=date)
    for fit_file in sorted(files):
        try:
            messages = decode_fit_file(fit_file)
            extracted = _extract_skin_temp(messages, date)
            merged.skin_temp_overnight.extend(extracted.skin_temp_overnight)
        except Exception as e:
            log.warning("Error parsing %s: %s", fit_file, e)
    return merged


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


def parse_all_days(data_dir: Path) -> list[DayData]:
    """Parse all metric types for all days — single directory scan."""
    files_by_day = get_files_by_day(data_dir)
    result: list[DayData] = []

    for date, day_files in sorted(files_by_day.items()):
        wellness_files = day_files.get("WELLNESS", [])
        offset = _extract_offset_from_files(wellness_files)
        day = DayData(
            date=date,
            utc_offset_hours=offset,
            wellness=parse_wellness_day(wellness_files, date),
            sleep=parse_sleep_day(day_files.get("SLEEP_DATA", []), date),
            hrv=parse_hrv_day(day_files.get("HRV_STATUS", []), date),
            skin_temp=parse_skin_temp_day(day_files.get("SKIN_TEMP", []), date),
        )
        if offset is not None:
            _shift_timestamps(day, offset)
        result.append(day)

    return result
