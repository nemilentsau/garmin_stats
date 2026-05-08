"""Pydantic contracts for Garmin analytics read models and API responses."""

from app.contracts.base import DefaultsRequired

# ---------------------------------------------------------------------------
# Tier 1 — Reading-level models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tier 2 — Day-level containers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tier 3 — API response models (match frontend TypeScript interfaces)
# ---------------------------------------------------------------------------

class HeartRateRawResponse(DefaultsRequired):
    days: list[str]
    heart_rate: list[HeartRateReading]
    resting_hr: list[RestingHRReading]


class StressRawResponse(DefaultsRequired):
    days: list[str]
    stress: list[StressReading]


class BodyBatteryRawResponse(DefaultsRequired):
    days: list[str]
    body_battery: list[BodyBatteryReading]


class SpO2RawResponse(DefaultsRequired):
    days: list[str]
    spo2: list[SpO2Reading]


class RespirationRawResponse(DefaultsRequired):
    days: list[str]
    respiration: list[RespirationReading]


class SleepResponse(DefaultsRequired):
    days: list[str]
    sleep_levels: list[SleepLevel]
    sleep_assessments: list[SleepAssessment]


class HrvResponse(DefaultsRequired):
    days: list[str]
    hrv_values: list[HrvValue]
    hrv_summaries: list[HrvSummary]


class SkinTempResponse(DefaultsRequired):
    days: list[str]
    skin_temp_overnight: list[SkinTempOvernight]


# Daily aggregate sub-models


class HRZoneBucket(DefaultsRequired):
    label: str
    min_bpm: int
    max_bpm: int | None = None
    count: int
    pct: float


class DailyHeartRateStats(DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    resting: int | None = None
    zones: list[HRZoneBucket] = []


class HeartRateRecovery(DefaultsRequired):
    baseline_resting_7d: float | None = None
    delta_from_baseline: float | None = None
    status: str | None = None


class HeartRateDataQuality(DefaultsRequired):
    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HRZoneDuration(DefaultsRequired):
    label: str
    min_bpm: int
    max_bpm: int | None = None
    minutes: float
    pct: float


class HeartRateInsight(DefaultsRequired):
    level: str
    title: str
    detail: str


class HeartRateInsightsResponse(DefaultsRequired):
    date: str
    day_stats: DailyHeartRateStats
    recovery: HeartRateRecovery
    zones: list[HRZoneDuration]
    quality: HeartRateDataQuality
    insights: list[HeartRateInsight] = []


class DailyMetricStats(DefaultsRequired):
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyBodyBatteryStats(DefaultsRequired):
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyHrvStats(DefaultsRequired):
    weekly_avg: float | None = None
    nightly_avg: float | None = None
    status: str | None = None


class HrvRecovery(DefaultsRequired):
    baseline_nightly_7d: float | None = None
    delta_nightly_from_baseline: float | None = None
    acute_gap_vs_weekly: float | None = None
    status: str | None = None


class HrvDataQuality(DefaultsRequired):
    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HrvIntradaySegment(DefaultsRequired):
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


class HrvStatusBucket(DefaultsRequired):
    label: str
    count: int
    pct: float


class HrvTrendBand(DefaultsRequired):
    nightly_typical_low: float | None = None
    nightly_typical_high: float | None = None


class HrvStreak(DefaultsRequired):
    current_status: str | None = None
    streak_days: int = 0
    worst_recent_streak: int = 0


class HrvLongBaseline(DefaultsRequired):
    baseline_30d: float | None = None
    delta_7d_vs_30d: float | None = None


class HrvBaselineBands(DefaultsRequired):
    baseline_low_upper: float | None = None
    baseline_balanced_lower: float | None = None
    baseline_balanced_upper: float | None = None
    five_min_high: float | None = None


class HrvDistributionBin(DefaultsRequired):
    bin_start: float
    bin_end: float
    count: int


class HrvDistribution(DefaultsRequired):
    bins: list[HrvDistributionBin] = []
    total_days: int = 0
    selected_value: float | None = None
    selected_percentile: float | None = None


class HrvTrajectory(DefaultsRequired):
    early_avg: float | None = None
    mid_avg: float | None = None
    late_avg: float | None = None
    direction: str | None = None  # "rising", "falling", "flat", or None


class HrvDayOfWeekBucket(DefaultsRequired):
    day: str             # "Mon", "Tue", ..., "Sun"
    day_index: int       # 0=Mon, 6=Sun
    avg_nightly: float | None = None
    sample_count: int = 0


class HrvInsight(DefaultsRequired):
    level: str
    title: str
    detail: str


class HrvInsightsResponse(DefaultsRequired):
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


class DailySleepStats(DefaultsRequired):
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None


class DailySkinTempStats(DefaultsRequired):
    deviation: float | None = None
    deviation_7_day: float | None = None
    nightly_value: float | None = None


class DailyMetric(DefaultsRequired):
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


class PeriodHeartRateStats(DefaultsRequired):
    avg: float | None = None
    avg_resting: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None
    zones: list[HRZoneBucket] = []


class PeriodMetricStats(DefaultsRequired):
    avg: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None


class PeriodHrvStats(DefaultsRequired):
    avg_nightly: float | None = None
    avg_weekly: float | None = None
    balanced_pct: float | None = None
    total_days: int = 0


class PeriodSpo2Stats(DefaultsRequired):
    avg: float | None = None
    lowest_min: float | None = None
    low_days: int = 0
    total_days: int = 0


class PeriodSkinTempStats(DefaultsRequired):
    avg_deviation: float | None = None
    max_deviation: float | None = None
    min_deviation: float | None = None
    avg_nightly: float | None = None
    days_tracked: int = 0


class PeriodSleepStats(DefaultsRequired):
    avg_score: float | None = None
    avg_deep_score: float | None = None
    days_tracked: int = 0


class PeriodBodyBatteryStats(DefaultsRequired):
    avg_min: float | None = None
    avg_max: float | None = None
    days_tracked: int = 0


class PeriodSummary(DefaultsRequired):
    heart_rate: PeriodHeartRateStats
    stress: PeriodMetricStats
    respiration: PeriodMetricStats
    hrv: PeriodHrvStats
    spo2: PeriodSpo2Stats
    skin_temp: PeriodSkinTempStats
    sleep: PeriodSleepStats
    body_battery: PeriodBodyBatteryStats


class DailyAggregatesResponse(DefaultsRequired):
    days: list[str]
    daily: list[DailyMetric]
    period_windows: dict[str, PeriodSummary] = {}


# ---------------------------------------------------------------------------
# Heart Rate Analysis models
# ---------------------------------------------------------------------------


class CircadianHRPoint(DefaultsRequired):
    hour: int
    avg_bpm: float | None = None
    sample_count: int = 0


class SleepingHRPoint(DefaultsRequired):
    date: str
    avg_sleeping_bpm: float | None = None
    ma7_bpm: float | None = None
    sample_count: int = 0


class RestingHRTrendPoint(DefaultsRequired):
    date: str
    resting_bpm: int | None = None
    ma7_bpm: float | None = None


class DailyAvgHRTrendPoint(DefaultsRequired):
    date: str
    avg_bpm: float | None = None
    ma7_bpm: float | None = None


class HRHistogramBin(DefaultsRequired):
    bin_start: int
    bin_end: int
    count: int


class HRDistributionResponse(DefaultsRequired):
    date: str
    bins: list[HRHistogramBin] = []
    sample_count: int = 0


class WeeklyRestingHRBox(DefaultsRequired):
    iso_week: str
    min_bpm: float | None = None
    q1_bpm: float | None = None
    median_bpm: float | None = None
    q3_bpm: float | None = None
    max_bpm: float | None = None
    day_count: int = 0


class HRPatternWindow(DefaultsRequired):
    """Pre-computed circadian profile for a time window."""
    circadian_profile: list[CircadianHRPoint] = []


class HeartRateAnalysisResponse(DefaultsRequired):
    sleeping_hr_trend: list[SleepingHRPoint] = []
    resting_hr_trend: list[RestingHRTrendPoint] = []
    daily_avg_trend: list[DailyAvgHRTrendPoint] = []
    weekly_boxplots: list[WeeklyRestingHRBox] = []
    pattern_windows: dict[str, HRPatternWindow] = {}


class NightlyHrvTrendPoint(DefaultsRequired):
    date: str
    nightly_avg: float | None = None
    ma7: float | None = None


class WeeklyHrvBox(DefaultsRequired):
    iso_week: str
    min_ms: float | None = None
    q1_ms: float | None = None
    median_ms: float | None = None
    q3_ms: float | None = None
    max_ms: float | None = None
    day_count: int = 0


class HrvPatternWindow(DefaultsRequired):
    """Pre-computed distribution + day-of-week for a time window."""
    distribution: HrvDistribution | None = None
    day_of_week: list[HrvDayOfWeekBucket] = []


class HrvAnalysisResponse(DefaultsRequired):
    nightly_trend: list[NightlyHrvTrendPoint] = []
    weekly_boxplots: list[WeeklyHrvBox] = []
    pattern_windows: dict[str, HrvPatternWindow] = {}  # "3M", "6M", "All"


# ---------------------------------------------------------------------------
# Sleep analysis models
# ---------------------------------------------------------------------------


class SleepTrendPoint(DefaultsRequired):
    date: str
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None
    ma7: float | None = None  # 7d MA of score


class WeeklySleepBox(DefaultsRequired):
    iso_week: str
    min_score: float | None = None
    q1_score: float | None = None
    median_score: float | None = None
    q3_score: float | None = None
    max_score: float | None = None
    day_count: int = 0


class SleepAnalysisResponse(DefaultsRequired):
    score_trend: list[SleepTrendPoint] = []
    weekly_boxplots: list[WeeklySleepBox] = []


# ---------------------------------------------------------------------------
# Stress analysis models
# ---------------------------------------------------------------------------


class StressTrendPoint(DefaultsRequired):
    date: str
    avg: float | None = None
    ma7: float | None = None


class WeeklyStressBox(DefaultsRequired):
    iso_week: str
    min_avg: float | None = None
    q1_avg: float | None = None
    median_avg: float | None = None
    q3_avg: float | None = None
    max_avg: float | None = None
    day_count: int = 0


class StressAnalysisResponse(DefaultsRequired):
    avg_trend: list[StressTrendPoint] = []
    weekly_boxplots: list[WeeklyStressBox] = []


# ---------------------------------------------------------------------------
# Body Battery analysis models
# ---------------------------------------------------------------------------


class BodyBatteryTrendPoint(DefaultsRequired):
    date: str
    min_val: int | None = None
    max_val: int | None = None
    ma7_min: float | None = None  # 7d MA of daily min


class WeeklyBodyBatteryBox(DefaultsRequired):
    iso_week: str
    min_val: float | None = None
    q1_val: float | None = None
    median_val: float | None = None
    q3_val: float | None = None
    max_val: float | None = None
    day_count: int = 0


class BodyBatteryAnalysisResponse(DefaultsRequired):
    trend: list[BodyBatteryTrendPoint] = []
    weekly_boxplots: list[WeeklyBodyBatteryBox] = []


# ---------------------------------------------------------------------------
# Dashboard overview models
# ---------------------------------------------------------------------------


class ReadinessScore(DefaultsRequired):
    score: int | None = None
    components: dict[str, float] = {}
    component_hints: dict[str, str] = {}  # human-readable explanation per component
    label: str | None = None  # "Ready", "Moderate", "Rest"


class CorrelationPoint(DefaultsRequired):
    date: str
    hrv_nightly: float
    other_value: float


class MetricCorrelation(DefaultsRequired):
    metric: str              # "sleep_score", "resting_hr"
    label: str               # "Sleep Score", "Resting HR"
    points: list[CorrelationPoint] = []
    r_value: float | None = None
    sample_count: int = 0


class TodayVitals(DefaultsRequired):
    resting_hr: int | None = None
    resting_hr_delta_7d: float | None = None
    nightly_hrv: float | None = None
    nightly_hrv_delta_7d: float | None = None
    hrv_status: str | None = None
    sleep_score: int | None = None
    stress_avg: float | None = None


class SparklinePoint(DefaultsRequired):
    date: str
    value: float | None = None
    ma7: float | None = None


class SparklineSummary(DefaultsRequired):
    avg: float | None = None
    min: float | None = None
    max: float | None = None


class SparklineSeries(DefaultsRequired):
    points: list[SparklinePoint] = []
    summary: SparklineSummary = SparklineSummary()


class DashboardSparklines(DefaultsRequired):
    resting_hr: SparklineSeries = SparklineSeries()
    nightly_hrv: SparklineSeries = SparklineSeries()
    sleep_score: SparklineSeries = SparklineSeries()
    stress_avg: SparklineSeries = SparklineSeries()


class DashboardOverviewResponse(DefaultsRequired):
    date: str
    readiness: ReadinessScore | None = None
    vitals: TodayVitals | None = None
    sparklines: DashboardSparklines | None = None
    correlations: list[MetricCorrelation] = []
