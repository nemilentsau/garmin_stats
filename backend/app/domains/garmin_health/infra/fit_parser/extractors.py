"""Per-file Garmin FIT message extractors.

Each extractor maps one decoded FIT file into the canonical Garmin health
contracts for that file type.  Cross-file day merging and timestamp offset
application live in sibling modules so these functions stay focused on field
selection, filtering, and Garmin SDK quirks.
"""

from app.domains.garmin_health.contracts import (
    ActivityReading,
    BodyBatteryReading,
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
from app.domains.garmin_health.infra.fit_parser.timestamps import (
    _GARMIN_EPOCH_UNIX,
    _resolve_timestamp_16,
    parse_datetime,
)


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

    ref_garmin: int | None = None

    for msg in messages.get("monitoring_mesgs", []):
        full_ts = msg.get("timestamp")
        if full_ts is not None and hasattr(full_ts, "timestamp"):
            ref_garmin = int(full_ts.timestamp()) - _GARMIN_EPOCH_UNIX

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
