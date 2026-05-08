"""Chart, trend, and distribution response contracts."""

from app.contracts.base import DefaultsRequired


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
