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
    utc_offset_hours: float | None = None
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


class HeartRateRecovery(_DefaultsRequired):
    baseline_resting_7d: float | None = None
    delta_from_baseline: float | None = None
    status: str | None = None


class HeartRateDataQuality(_DefaultsRequired):
    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HRZoneDuration(_DefaultsRequired):
    label: str
    min_bpm: int
    max_bpm: int | None = None
    minutes: float
    pct: float


class HeartRateInsight(_DefaultsRequired):
    level: str
    title: str
    detail: str


class HeartRateInsightsResponse(_DefaultsRequired):
    date: str
    day_stats: DailyHeartRateStats
    recovery: HeartRateRecovery
    zones: list[HRZoneDuration]
    quality: HeartRateDataQuality
    insights: list[HeartRateInsight] = []


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


class HrvRecovery(_DefaultsRequired):
    baseline_nightly_7d: float | None = None
    delta_nightly_from_baseline: float | None = None
    acute_gap_vs_weekly: float | None = None
    status: str | None = None


class HrvDataQuality(_DefaultsRequired):
    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HrvIntradaySegment(_DefaultsRequired):
    key: str
    label: str
    sample_count: int = 0
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    stdev: float | None = None
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None
    values: list[HrvValue] = []


class HrvStatusBucket(_DefaultsRequired):
    label: str
    count: int
    pct: float


class HrvTrendBand(_DefaultsRequired):
    nightly_typical_low: float | None = None
    nightly_typical_high: float | None = None


class HrvStreak(_DefaultsRequired):
    current_status: str | None = None
    streak_days: int = 0
    worst_recent_streak: int = 0


class HrvLongBaseline(_DefaultsRequired):
    baseline_30d: float | None = None
    delta_7d_vs_30d: float | None = None


class HrvBaselineBands(_DefaultsRequired):
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    five_min_high: float | None = None


class HrvDistributionBin(_DefaultsRequired):
    bin_start: float
    bin_end: float
    count: int


class HrvDistribution(_DefaultsRequired):
    bins: list[HrvDistributionBin] = []
    total_days: int = 0
    selected_value: float | None = None
    selected_percentile: float | None = None


class HrvTrajectory(_DefaultsRequired):
    early_avg: float | None = None
    mid_avg: float | None = None
    late_avg: float | None = None
    direction: str | None = None  # "rising", "falling", "flat", or None


class HrvDayOfWeekBucket(_DefaultsRequired):
    day: str             # "Mon", "Tue", ..., "Sun"
    day_index: int       # 0=Mon, 6=Sun
    avg_nightly: float | None = None
    sample_count: int = 0


class HrvInsight(_DefaultsRequired):
    level: str
    title: str
    detail: str


class HrvInsightsResponse(_DefaultsRequired):
    date: str
    day_stats: DailyHrvStats
    recovery: HrvRecovery
    quality: HrvDataQuality
    intraday_segments: list[HrvIntradaySegment] = []
    trend_band: HrvTrendBand
    streak: HrvStreak | None = None
    long_baseline: HrvLongBaseline | None = None
    baseline_bands: HrvBaselineBands | None = None
    distribution: HrvDistribution | None = None
    trajectory: HrvTrajectory | None = None
    status_mix: list[HrvStatusBucket] = []
    day_of_week: list[HrvDayOfWeekBucket] = []
    insights: list[HrvInsight] = []


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
    utc_offset_hours: float | None = None
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


# ---------------------------------------------------------------------------
# Heart Rate Analysis models
# ---------------------------------------------------------------------------


class CircadianHRPoint(_DefaultsRequired):
    hour: int
    avg_bpm: float | None = None
    sample_count: int = 0


class SleepingHRPoint(_DefaultsRequired):
    date: str
    avg_sleeping_bpm: float | None = None
    ma7_bpm: float | None = None
    sample_count: int = 0


class RestingHRTrendPoint(_DefaultsRequired):
    date: str
    resting_bpm: int | None = None
    ma7_bpm: float | None = None


class DailyAvgHRTrendPoint(_DefaultsRequired):
    date: str
    avg_bpm: float | None = None
    ma7_bpm: float | None = None


class HRHistogramBin(_DefaultsRequired):
    bin_start: int
    bin_end: int
    count: int


class HRDistributionResponse(_DefaultsRequired):
    date: str
    bins: list[HRHistogramBin] = []
    sample_count: int = 0


class WeeklyRestingHRBox(_DefaultsRequired):
    iso_week: str
    min_bpm: float | None = None
    q1_bpm: float | None = None
    median_bpm: float | None = None
    q3_bpm: float | None = None
    max_bpm: float | None = None
    day_count: int = 0


class HeartRateAnalysisResponse(_DefaultsRequired):
    circadian_profile: list[CircadianHRPoint] = []
    sleeping_hr_trend: list[SleepingHRPoint] = []
    resting_hr_trend: list[RestingHRTrendPoint] = []
    daily_avg_trend: list[DailyAvgHRTrendPoint] = []
    weekly_boxplots: list[WeeklyRestingHRBox] = []


class NightlyHrvTrendPoint(_DefaultsRequired):
    date: str
    nightly_avg: float | None = None
    ma7: float | None = None


class WeeklyHrvBox(_DefaultsRequired):
    iso_week: str
    min_ms: float | None = None
    q1_ms: float | None = None
    median_ms: float | None = None
    q3_ms: float | None = None
    max_ms: float | None = None
    day_count: int = 0


class HrvPatternWindow(_DefaultsRequired):
    """Pre-computed distribution + day-of-week for a time window."""
    distribution: HrvDistribution | None = None
    day_of_week: list[HrvDayOfWeekBucket] = []


class HrvAnalysisResponse(_DefaultsRequired):
    nightly_trend: list[NightlyHrvTrendPoint] = []
    weekly_boxplots: list[WeeklyHrvBox] = []
    pattern_windows: dict[str, HrvPatternWindow] = {}  # "3M", "6M", "All"


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


# ---------------------------------------------------------------------------
# Dashboard overview models
# ---------------------------------------------------------------------------


class ReadinessScore(_DefaultsRequired):
    score: int | None = None
    components: dict[str, float] = {}
    label: str | None = None  # "Ready", "Moderate", "Rest"


class CorrelationPoint(_DefaultsRequired):
    date: str
    hrv_nightly: float
    other_value: float


class MetricCorrelation(_DefaultsRequired):
    metric: str              # "sleep_score", "resting_hr"
    label: str               # "Sleep Score", "Resting HR"
    points: list[CorrelationPoint] = []
    r_value: float | None = None
    sample_count: int = 0


class DashboardOverviewResponse(_DefaultsRequired):
    date: str
    readiness: ReadinessScore | None = None
    correlations: list[MetricCorrelation] = []
