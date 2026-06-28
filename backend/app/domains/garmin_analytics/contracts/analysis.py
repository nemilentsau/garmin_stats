"""Chart, trend, and distribution response contracts."""

from enum import IntEnum

from app.contracts.base import DefaultsRequired


class BaselineWindow(IntEnum):
    """Allowed trailing baseline windows (days) for HRV surfaces."""

    D30 = 30
    D60 = 60
    D90 = 90


# Single source of truth for the default baseline window. Referenced by the application
# loaders, the HrvBaseline contract default, and the trends primitive (which re-exports it)
# so the product default lives in exactly one place.
BASELINE_WINDOW_DEFAULT = 60


class CircadianHRPoint(DefaultsRequired):
    """Average heart rate for one hour of day."""

    hour: int
    avg_bpm: float | None = None
    sample_count: int = 0


class SleepingHRPoint(DefaultsRequired):
    """Daily sleeping heart-rate trend point."""

    date: str
    avg_sleeping_bpm: float | None = None
    ma7_bpm: float | None = None
    sample_count: int = 0


class RestingHRTrendPoint(DefaultsRequired):
    """Daily resting heart-rate trend point."""

    date: str
    resting_bpm: int | None = None
    ma7_bpm: float | None = None


class DailyAvgHRTrendPoint(DefaultsRequired):
    """Daily average heart-rate trend point."""

    date: str
    avg_bpm: float | None = None
    ma7_bpm: float | None = None


class HRHistogramBin(DefaultsRequired):
    """One histogram bin for heart-rate readings."""

    bin_start: int
    bin_end: int
    count: int


class HRDistributionResponse(DefaultsRequired):
    """Selected-day heart-rate distribution response."""

    date: str
    bins: list[HRHistogramBin] = []
    sample_count: int = 0


class WeeklyRestingHRBox(DefaultsRequired):
    """Weekly five-number summary for resting heart rate."""

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
    """Heart-rate chart and distribution analysis response."""

    sleeping_hr_trend: list[SleepingHRPoint] = []
    resting_hr_trend: list[RestingHRTrendPoint] = []
    daily_avg_trend: list[DailyAvgHRTrendPoint] = []
    weekly_boxplots: list[WeeklyRestingHRBox] = []
    pattern_windows: dict[str, HRPatternWindow] = {}


class HrvDayOfWeekBucket(DefaultsRequired):
    """Average nightly HRV for one weekday."""

    day: str             # "Mon", "Tue", ..., "Sun"
    day_index: int       # 0=Mon, 6=Sun
    avg_nightly: float | None = None
    sample_count: int = 0


class NightlyHrvTrendPoint(DefaultsRequired):
    """Daily nightly-HRV trend point with its trailing robust baseline."""

    date: str
    nightly_avg: float | None = None
    ma7: float | None = None
    band_low: float | None = None
    band_high: float | None = None
    z: float | None = None
    is_extreme: bool = False


class HrvPatternWindow(DefaultsRequired):
    """Pre-computed day-of-week HRV pattern for a time window.

    ``overall_avg`` is the sample-weighted mean of all present nightly HRV values
    in the window (true grand mean, not a mean-of-weekday-means). ``total_sample_count``
    is the number of nights represented across the weekday buckets (the sum of their
    ``sample_count`` values). Both are provided so the frontend can show a
    backend-authoritative reference and total without doing any aggregation itself.
    """

    day_of_week: list[HrvDayOfWeekBucket] = []
    overall_avg: float | None = None
    total_sample_count: int = 0


class HrvAnalysisResponse(DefaultsRequired):
    """HRV chart and pattern analysis response."""

    nightly_trend: list[NightlyHrvTrendPoint] = []
    pattern_windows: dict[str, HrvPatternWindow] = {}  # "3M", "6M", "All"


class SleepTrendPoint(DefaultsRequired):
    """Daily sleep score trend point."""

    date: str
    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None
    ma7: float | None = None  # 7d MA of score


class WeeklySleepBox(DefaultsRequired):
    """Weekly five-number summary for sleep score."""

    iso_week: str
    min_score: float | None = None
    q1_score: float | None = None
    median_score: float | None = None
    q3_score: float | None = None
    max_score: float | None = None
    day_count: int = 0


class SleepAnalysisResponse(DefaultsRequired):
    """Sleep chart and distribution analysis response."""

    score_trend: list[SleepTrendPoint] = []
    weekly_boxplots: list[WeeklySleepBox] = []


class StressTrendPoint(DefaultsRequired):
    """Daily stress trend point."""

    date: str
    avg: float | None = None
    ma7: float | None = None


class WeeklyStressBox(DefaultsRequired):
    """Weekly five-number summary for average stress."""

    iso_week: str
    min_avg: float | None = None
    q1_avg: float | None = None
    median_avg: float | None = None
    q3_avg: float | None = None
    max_avg: float | None = None
    day_count: int = 0


class StressAnalysisResponse(DefaultsRequired):
    """Stress chart and distribution analysis response."""

    avg_trend: list[StressTrendPoint] = []
    weekly_boxplots: list[WeeklyStressBox] = []


class BodyBatteryTrendPoint(DefaultsRequired):
    """Daily Body Battery min/max trend point."""

    date: str
    min_val: int | None = None
    max_val: int | None = None
    ma7_min: float | None = None  # 7d MA of daily min


class WeeklyBodyBatteryBox(DefaultsRequired):
    """Weekly five-number summary for Body Battery minimum."""

    iso_week: str
    min_val: float | None = None
    q1_val: float | None = None
    median_val: float | None = None
    q3_val: float | None = None
    max_val: float | None = None
    day_count: int = 0


class BodyBatteryAnalysisResponse(DefaultsRequired):
    """Body Battery chart and distribution analysis response."""

    trend: list[BodyBatteryTrendPoint] = []
    weekly_boxplots: list[WeeklyBodyBatteryBox] = []
