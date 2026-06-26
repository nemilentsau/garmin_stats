"""Selected-day insight response contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import (
    DailyHeartRateStats,
    DailyHrvStats,
    HrvValue,
)

from .analysis import (
    HrvDayOfWeekBucket,
    HrvDistribution,
)


class HeartRateRecovery(DefaultsRequired):
    """Selected-day resting-HR recovery comparison."""

    baseline_resting_7d: float | None = None
    delta_from_baseline: float | None = None
    status: str | None = None


class HeartRateDataQuality(DefaultsRequired):
    """Coverage summary for selected-day heart-rate readings."""

    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HRZoneDuration(DefaultsRequired):
    """Estimated time spent in one heart-rate zone."""

    label: str
    min_bpm: int
    max_bpm: int | None = None
    minutes: float
    pct: float


class HeartRateInsight(DefaultsRequired):
    """One selected-day heart-rate insight message."""

    level: str
    title: str
    detail: str


class HeartRateInsightsResponse(DefaultsRequired):
    """Selected-day heart-rate insight response."""

    date: str
    day_stats: DailyHeartRateStats
    recovery: HeartRateRecovery
    zones: list[HRZoneDuration]
    quality: HeartRateDataQuality
    insights: list[HeartRateInsight] = []


class HrvRecovery(DefaultsRequired):
    """Selected-day HRV recovery comparison."""

    baseline_nightly_7d: float | None = None
    delta_nightly_from_baseline: float | None = None
    acute_gap_vs_weekly: float | None = None
    status: str | None = None


class HrvDataQuality(DefaultsRequired):
    """Coverage summary for selected-day HRV readings."""

    sample_count: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_hours: float | None = None


class HrvIntradaySegment(DefaultsRequired):
    """Aggregated HRV stats for one intraday segment."""

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


class HrvTrendBand(DefaultsRequired):
    """Typical nightly HRV band across the analysis window."""

    nightly_typical_low: float | None = None
    nightly_typical_high: float | None = None


class HrvStreak(DefaultsRequired):
    """Current and recent HRV status streak information."""

    current_status: str | None = None
    streak_days: int = 0
    worst_recent_streak: int = 0


class HrvLongBaseline(DefaultsRequired):
    """Longer baseline comparison for recent HRV trend."""

    baseline_30d: float | None = None
    delta_7d_vs_30d: float | None = None


class HrvInsight(DefaultsRequired):
    """One selected-day HRV insight message."""

    level: str
    title: str
    detail: str


class HrvInsightsResponse(DefaultsRequired):
    """Selected-day HRV insight response."""

    date: str
    day_stats: DailyHrvStats
    recovery: HrvRecovery
    quality: HrvDataQuality
    intraday_segments: list[HrvIntradaySegment] = []
    trend_band: HrvTrendBand
    streak: HrvStreak | None = None
    long_baseline: HrvLongBaseline | None = None
    distribution: HrvDistribution | None = None
    day_of_week: list[HrvDayOfWeekBucket] = []
    insights: list[HrvInsight] = []
