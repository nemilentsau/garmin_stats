"""
Pydantic models for Garmin Stats — three tiers:

  Tier 1: Reading-level atoms (parser output)
  Tier 2: Day-level containers (parser output)
  Tier 3: API response models (match frontend TS interfaces)
"""

from pydantic import BaseModel, ConfigDict


class _DefaultsRequired(BaseModel):
    """Base for models where all fields (even those with defaults) should appear
    as 'required' in the JSON schema serialization output.  This ensures
    openapi-typescript generates `prop: T | null` instead of `prop?: T | null`."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


# ---------------------------------------------------------------------------
# Tier 1 — Reading-level models
# ---------------------------------------------------------------------------

class HeartRateReading(_DefaultsRequired):
    timestamp: str | None = None
    value: int


class StressReading(_DefaultsRequired):
    timestamp: str
    value: int


class SpO2Reading(_DefaultsRequired):
    timestamp: str
    value: int
    confidence: int | None = None
    mode: str


class RespirationReading(_DefaultsRequired):
    timestamp: str
    value: float


class ActivityReading(_DefaultsRequired):
    timestamp: str | None = None
    activity_type: str
    intensity: int | None = None
    steps: int | None = None
    calories: int | None = None
    distance: float | None = None


class StepsReading(_DefaultsRequired):
    timestamp: str | None = None
    steps: int
    distance: float | None = None
    calories: int | None = None


class RestingHRReading(_DefaultsRequired):
    timestamp: str
    resting_hr: int | None = None
    current_day_resting_hr: int | None = None


class SleepLevel(_DefaultsRequired):
    date: str
    timestamp: str
    level: str


class SleepAssessment(_DefaultsRequired):
    date: str
    overall_score: int | None = None
    deep_sleep_score: int | None = None
    light_sleep_score: int | None = None
    rem_sleep_score: int | None = None
    awake_time_score: int | None = None
    awakenings_count: int | None = None
    average_stress: float | None = None


class HrvValue(_DefaultsRequired):
    date: str
    timestamp: str
    value: float


class HrvSummary(_DefaultsRequired):
    date: str
    weekly_average: float | None = None
    last_night_average: float | None = None
    last_night_5_min_high: float | None = None
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    status: str


class SkinTempOvernight(_DefaultsRequired):
    date: str
    timestamp: str | None = None
    local_timestamp: float | None = None
    nightly_value: float | None = None
    average_deviation: float | None = None
    average_7_day_deviation: float | None = None


# ---------------------------------------------------------------------------
# Tier 2 — Day-level containers
# ---------------------------------------------------------------------------

class DayWellness(_DefaultsRequired):
    date: str
    heart_rate: list[HeartRateReading] = []
    stress: list[StressReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps_summary: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []


class DaySleep(_DefaultsRequired):
    date: str
    sleep_levels: list[SleepLevel] = []
    sleep_assessments: list[SleepAssessment] = []


class DayHrv(_DefaultsRequired):
    date: str
    hrv_values: list[HrvValue] = []
    hrv_summaries: list[HrvSummary] = []


class DaySkinTemp(_DefaultsRequired):
    date: str
    skin_temp_overnight: list[SkinTempOvernight] = []


class DayData(_DefaultsRequired):
    date: str
    wellness: DayWellness
    sleep: DaySleep
    hrv: DayHrv
    skin_temp: DaySkinTemp


# ---------------------------------------------------------------------------
# Tier 3 — API response models (match frontend TypeScript interfaces)
# ---------------------------------------------------------------------------

class WellnessResponse(_DefaultsRequired):
    days: list[str]
    heart_rate: list[HeartRateReading]
    stress: list[StressReading]
    spo2: list[SpO2Reading]
    respiration: list[RespirationReading]
    activity: list[ActivityReading]
    steps_summary: list[StepsReading]
    resting_hr: list[RestingHRReading]


class SleepResponse(_DefaultsRequired):
    days: list[str]
    sleep_levels: list[SleepLevel]
    sleep_assessments: list[SleepAssessment]


class HrvResponse(_DefaultsRequired):
    days: list[str]
    hrv_values: list[HrvValue]
    hrv_summaries: list[HrvSummary]


class SkinTempResponse(_DefaultsRequired):
    days: list[str]
    skin_temp_overnight: list[SkinTempOvernight]


# Daily aggregate sub-models

class DailyHeartRateStats(_DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    resting: int | None = None


class DailyMetricStats(_DefaultsRequired):
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyHrvStats(_DefaultsRequired):
    weekly_avg: float | None = None
    nightly_avg: float | None = None
    status: str | None = None


class DailySleepStats(_DefaultsRequired):
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None


class DailySkinTempStats(_DefaultsRequired):
    deviation: float | None = None
    deviation_7_day: float | None = None
    nightly_value: float | None = None


class DailyMetric(_DefaultsRequired):
    date: str
    heart_rate: DailyHeartRateStats
    stress: DailyMetricStats
    spo2: DailyMetricStats
    respiration: DailyMetricStats
    hrv: DailyHrvStats
    sleep: DailySleepStats
    skin_temp: DailySkinTempStats


class DailyAggregatesResponse(_DefaultsRequired):
    days: list[str]
    daily: list[DailyMetric]


class DaySummaryResponse(_DefaultsRequired):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(_DefaultsRequired):
    days: list[str]
    total: int
