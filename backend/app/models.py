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
    timestamp: str | None = None
    value: int


class BodyBatteryReading(_DefaultsRequired):
    timestamp: str | None = None
    value: int


class SpO2Reading(_DefaultsRequired):
    timestamp: str | None = None
    value: int
    confidence: int | None = None
    mode: str


class RespirationReading(_DefaultsRequired):
    timestamp: str | None = None
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
    timestamp: str | None = None
    resting_hr: int | None = None
    current_day_resting_hr: int | None = None


class SleepLevel(_DefaultsRequired):
    date: str
    timestamp: str | None = None
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
    timestamp: str | None = None
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
    body_battery: list[BodyBatteryReading] = []
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
    body_battery: list[BodyBatteryReading]
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


class HRZoneBucket(_DefaultsRequired):
    label: str
    min_bpm: int
    max_bpm: int | None = None
    count: int
    pct: float


class DailyHeartRateStats(_DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    resting: int | None = None
    zones: list[HRZoneBucket] = []


class DailyMetricStats(_DefaultsRequired):
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyBodyBatteryStats(_DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
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
    body_battery: DailyBodyBatteryStats
    spo2: DailyMetricStats
    respiration: DailyMetricStats
    hrv: DailyHrvStats
    sleep: DailySleepStats
    skin_temp: DailySkinTempStats


class PeriodHeartRateStats(_DefaultsRequired):
    avg: float | None = None
    avg_resting: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None
    zones: list[HRZoneBucket] = []


class PeriodMetricStats(_DefaultsRequired):
    avg: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None


class PeriodHrvStats(_DefaultsRequired):
    avg_nightly: float | None = None
    avg_weekly: float | None = None
    balanced_pct: float | None = None
    total_days: int = 0


class PeriodSpo2Stats(_DefaultsRequired):
    avg: float | None = None
    lowest_min: float | None = None
    low_days: int = 0
    total_days: int = 0


class PeriodSkinTempStats(_DefaultsRequired):
    avg_deviation: float | None = None
    max_deviation: float | None = None
    min_deviation: float | None = None
    avg_nightly: float | None = None
    days_tracked: int = 0


class PeriodSummary(_DefaultsRequired):
    heart_rate: PeriodHeartRateStats
    stress: PeriodMetricStats
    respiration: PeriodMetricStats
    hrv: PeriodHrvStats
    spo2: PeriodSpo2Stats
    skin_temp: PeriodSkinTempStats


class DailyAggregatesResponse(_DefaultsRequired):
    days: list[str]
    daily: list[DailyMetric]
    period: PeriodSummary | None = None


class DaySummaryResponse(_DefaultsRequired):
    date: str
    total_files: int
    file_types: dict[str, int]
    total_size_kb: float


class DaysResponse(_DefaultsRequired):
    days: list[str]
    total: int


class IngestResult(_DefaultsRequired):
    days_ingested: int
    duration_ms: int


class IngestStatus(_DefaultsRequired):
    needs_ingest: bool
    last_ingest_time: str | None = None
    days_in_db: int
    days_on_disk: int
