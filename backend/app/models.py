"""
Pydantic models for Garmin Stats — three tiers:

  Tier 1: Reading-level atoms (parser output)
  Tier 2: Day-level containers (parser output)
  Tier 3: API response models (match frontend TS interfaces)
"""

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Tier 1 — Reading-level models
# ---------------------------------------------------------------------------

class HeartRateReading(BaseModel):
    timestamp: str | None = None
    value: int


class StressReading(BaseModel):
    timestamp: str
    value: int


class SpO2Reading(BaseModel):
    timestamp: str
    value: int
    confidence: int | None = None
    mode: str


class RespirationReading(BaseModel):
    timestamp: str
    value: float


class ActivityReading(BaseModel):
    timestamp: str | None = None
    activity_type: str
    intensity: int | None = None
    steps: int | None = None
    calories: int | None = None
    distance: float | None = None


class StepsReading(BaseModel):
    timestamp: str | None = None
    steps: int
    distance: float | None = None
    calories: int | None = None


class RestingHRReading(BaseModel):
    timestamp: str
    resting_hr: int | None = None
    current_day_resting_hr: int | None = None


class SleepLevel(BaseModel):
    date: str
    timestamp: str
    level: str


class SleepAssessment(BaseModel):
    date: str
    overall_score: int | None = None
    deep_sleep_score: int | None = None
    light_sleep_score: int | None = None
    rem_sleep_score: int | None = None
    awake_time_score: int | None = None
    awakenings_count: int | None = None
    average_stress: float | None = None


class HrvValue(BaseModel):
    date: str
    timestamp: str
    value: float


class HrvSummary(BaseModel):
    date: str
    weekly_average: float | None = None
    last_night_average: float | None = None
    last_night_5_min_high: float | None = None
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    status: str


class SkinTempOvernight(BaseModel):
    date: str
    timestamp: str | None = None
    local_timestamp: float | None = None
    nightly_value: float | None = None
    average_deviation: float | None = None
    average_7_day_deviation: float | None = None


# ---------------------------------------------------------------------------
# Tier 2 — Day-level containers
# ---------------------------------------------------------------------------

class DayWellness(BaseModel):
    date: str
    heart_rate: list[HeartRateReading] = []
    stress: list[StressReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps_summary: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []


class DaySleep(BaseModel):
    date: str
    sleep_levels: list[SleepLevel] = []
    sleep_assessments: list[SleepAssessment] = []


class DayHrv(BaseModel):
    date: str
    hrv_values: list[HrvValue] = []
    hrv_summaries: list[HrvSummary] = []


class DaySkinTemp(BaseModel):
    date: str
    skin_temp_overnight: list[SkinTempOvernight] = []


class DayData(BaseModel):
    date: str
    wellness: DayWellness
    sleep: DaySleep
    hrv: DayHrv
    skin_temp: DaySkinTemp


# ---------------------------------------------------------------------------
# Tier 3 — API response models (match frontend TypeScript interfaces)
# ---------------------------------------------------------------------------

class WellnessResponse(BaseModel):
    days: list[str]
    heart_rate: list[HeartRateReading]
    stress: list[StressReading]
    spo2: list[SpO2Reading]
    respiration: list[RespirationReading]
    activity: list[ActivityReading]
    steps_summary: list[StepsReading]
    resting_hr: list[RestingHRReading]


class SleepResponse(BaseModel):
    days: list[str]
    sleep_levels: list[SleepLevel]
    sleep_assessments: list[SleepAssessment]


class HrvResponse(BaseModel):
    days: list[str]
    hrv_values: list[HrvValue]
    hrv_summaries: list[HrvSummary]


class SkinTempResponse(BaseModel):
    days: list[str]
    skin_temp_overnight: list[SkinTempOvernight]


# Daily aggregate sub-models

class DailyHeartRateStats(BaseModel):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    resting: int | None = None


class DailyMetricStats(BaseModel):
    avg: float | None = None
    min: float | None = None
    max: float | None = None


class DailyHrvStats(BaseModel):
    weekly_avg: float | None = None
    nightly_avg: float | None = None
    status: str | None = None


class DailySleepStats(BaseModel):
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None


class DailySkinTempStats(BaseModel):
    deviation: float | None = None
    deviation_7_day: float | None = None
    nightly_value: float | None = None


class DailyMetric(BaseModel):
    date: str
    heart_rate: DailyHeartRateStats
    stress: DailyMetricStats
    spo2: DailyMetricStats
    respiration: DailyMetricStats
    hrv: DailyHrvStats
    sleep: DailySleepStats
    skin_temp: DailySkinTempStats


class DailyAggregatesResponse(BaseModel):
    days: list[str]
    daily: list[DailyMetric]


class DaySummaryResponse(BaseModel):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(BaseModel):
    days: list[str]
    total: int
