"""Selected-day insight response contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_analytics.contracts.analysis import BASELINE_WINDOW_DEFAULT
from app.domains.garmin_health.contracts import (
    DailyHeartRateStats,
    DailyHrvStats,
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


class HrvStreak(DefaultsRequired):
    """Current HRV status streak — an internal input to the low-streak insight rule.

    Not serialized on any response; consumed only by ``low_status_streak_rule`` to decide
    whether to emit the "Extended low HRV streak" insight.
    """

    current_status: str | None = None
    streak_days: int = 0


class HrvBaseline(DefaultsRequired):
    """Selected-day comparison against the trailing robust baseline."""

    baseline: float | None = None
    delta_7d_vs_baseline: float | None = None
    window_days: int = BASELINE_WINDOW_DEFAULT
    selected_z: float | None = None
    selected_is_extreme: bool = False


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
    baseline: HrvBaseline | None = None
    insights: list[HrvInsight] = []
