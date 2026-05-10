"""Canonical parsed Garmin reading rows and day-level containers."""

from app.contracts.base import DefaultsRequired


class HeartRateReading(DefaultsRequired):
    """Parsed heart-rate sample in local time."""

    timestamp: str | None = None
    value: int


class StressReading(DefaultsRequired):
    """Parsed Garmin stress sample in local time."""

    timestamp: str | None = None
    value: int


class BodyBatteryReading(DefaultsRequired):
    """Parsed Body Battery sample in local time."""

    timestamp: str | None = None
    value: int


class SpO2Reading(DefaultsRequired):
    """Parsed pulse-ox sample with Garmin confidence metadata."""

    timestamp: str | None = None
    value: int
    confidence: int | None = None
    mode: str


class RespirationReading(DefaultsRequired):
    """Parsed respiration-rate sample in local time."""

    timestamp: str | None = None
    value: float


class ActivityReading(DefaultsRequired):
    """Parsed activity summary sample from wellness FIT records."""

    timestamp: str | None = None
    activity_type: str
    intensity: int | None = None
    steps: int | None = None
    calories: int | None = None
    distance: float | None = None


class StepsReading(DefaultsRequired):
    """Parsed step summary sample from wellness FIT records."""

    timestamp: str | None = None
    steps: int
    distance: float | None = None
    calories: int | None = None


class RestingHRReading(DefaultsRequired):
    """Parsed Garmin resting-heart-rate sample."""

    timestamp: str | None = None
    resting_hr: int | None = None
    current_day_resting_hr: int | None = None


class SleepLevel(DefaultsRequired):
    """Parsed sleep-stage interval marker for one local date."""

    date: str
    timestamp: str | None = None
    level: str


class SleepAssessment(DefaultsRequired):
    """Parsed Garmin sleep score assessment for one local date."""

    date: str
    overall_score: int | None = None
    deep_sleep_score: int | None = None
    light_sleep_score: int | None = None
    rem_sleep_score: int | None = None
    awake_time_score: int | None = None
    awakenings_count: int | None = None
    average_stress: float | None = None


class HrvValue(DefaultsRequired):
    """Parsed intraday HRV sample for one local date."""

    date: str
    timestamp: str | None = None
    value: float


class HrvSummary(DefaultsRequired):
    """Parsed Garmin overnight HRV summary and baseline status."""

    date: str
    weekly_average: float | None = None
    last_night_average: float | None = None
    last_night_5_min_high: float | None = None
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    status: str


class SkinTempOvernight(DefaultsRequired):
    """Parsed overnight skin-temperature summary for one local date."""

    date: str
    timestamp: str | None = None
    local_timestamp: float | None = None
    nightly_value: float | None = None
    average_deviation: float | None = None
    average_7_day_deviation: float | None = None


class DayWellness(DefaultsRequired):
    """All parsed wellness rows for one local Garmin date."""

    date: str
    heart_rate: list[HeartRateReading] = []
    stress: list[StressReading] = []
    body_battery: list[BodyBatteryReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps_summary: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []


class DaySleep(DefaultsRequired):
    """All parsed sleep rows for one local Garmin date."""

    date: str
    sleep_levels: list[SleepLevel] = []
    sleep_assessments: list[SleepAssessment] = []


class DayHrv(DefaultsRequired):
    """All parsed HRV rows for one local Garmin date."""

    date: str
    hrv_values: list[HrvValue] = []
    hrv_summaries: list[HrvSummary] = []


class DaySkinTemp(DefaultsRequired):
    """All parsed skin-temperature rows for one local Garmin date."""

    date: str
    skin_temp_overnight: list[SkinTempOvernight] = []


class DayData(DefaultsRequired):
    """Parsed Garmin health data grouped by one local date."""

    date: str
    utc_offset_hours: float | None = None
    wellness: DayWellness
    sleep: DaySleep
    hrv: DayHrv
    skin_temp: DaySkinTemp
