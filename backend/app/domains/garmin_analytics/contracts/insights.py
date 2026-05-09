"""Selected-day insight response contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import (
    DailyHeartRateStats,
    DailyHrvStats,
    HrvValue,
)

from .analysis import (
    HrvBaselineBands,
    HrvDayOfWeekBucket,
    HrvDistribution,
    HrvTrajectory,
)


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
