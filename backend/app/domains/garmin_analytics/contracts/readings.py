"""Persisted Garmin reading rows and day-level biometric containers."""

from app.contracts.base import DefaultsRequired


class HeartRateReading(DefaultsRequired):
    timestamp: str | None = None
    value: int


class StressReading(DefaultsRequired):
    timestamp: str | None = None
    value: int


class BodyBatteryReading(DefaultsRequired):
    timestamp: str | None = None
    value: int


class SpO2Reading(DefaultsRequired):
    timestamp: str | None = None
    value: int
    confidence: int | None = None
    mode: str


class RespirationReading(DefaultsRequired):
    timestamp: str | None = None
    value: float


class ActivityReading(DefaultsRequired):
    timestamp: str | None = None
    activity_type: str
    intensity: int | None = None
    steps: int | None = None
    calories: int | None = None
    distance: float | None = None


class StepsReading(DefaultsRequired):
    timestamp: str | None = None
    steps: int
    distance: float | None = None
    calories: int | None = None


class RestingHRReading(DefaultsRequired):
    timestamp: str | None = None
    resting_hr: int | None = None
    current_day_resting_hr: int | None = None


class SleepLevel(DefaultsRequired):
    date: str
    timestamp: str | None = None
    level: str


class SleepAssessment(DefaultsRequired):
    date: str
    overall_score: int | None = None
    deep_sleep_score: int | None = None
    light_sleep_score: int | None = None
    rem_sleep_score: int | None = None
    awake_time_score: int | None = None
    awakenings_count: int | None = None
    average_stress: float | None = None


class HrvValue(DefaultsRequired):
    date: str
    timestamp: str | None = None
    value: float


class HrvSummary(DefaultsRequired):
    date: str
    weekly_average: float | None = None
    last_night_average: float | None = None
    last_night_5_min_high: float | None = None
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    status: str


class SkinTempOvernight(DefaultsRequired):
    date: str
    timestamp: str | None = None
    local_timestamp: float | None = None
    nightly_value: float | None = None
    average_deviation: float | None = None
    average_7_day_deviation: float | None = None


class DayWellness(DefaultsRequired):
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
    date: str
    sleep_levels: list[SleepLevel] = []
    sleep_assessments: list[SleepAssessment] = []


class DayHrv(DefaultsRequired):
    date: str
    hrv_values: list[HrvValue] = []
    hrv_summaries: list[HrvSummary] = []


class DaySkinTemp(DefaultsRequired):
    date: str
    skin_temp_overnight: list[SkinTempOvernight] = []


class DayData(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    wellness: DayWellness
    sleep: DaySleep
    hrv: DayHrv
    skin_temp: DaySkinTemp
