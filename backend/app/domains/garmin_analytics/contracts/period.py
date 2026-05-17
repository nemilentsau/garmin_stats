"""Period-window Garmin summary contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    HRZoneBucket,
)


class PeriodHeartRateStats(DefaultsRequired):
    """Heart-rate summary recomputed from raw readings across a period."""

    avg: float | None = None
    avg_resting: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None
    zones: list[HRZoneBucket] = []


class PeriodMetricStats(DefaultsRequired):
    """Common scalar metric summary recomputed across a period."""

    avg: float | None = None
    typical_low: float | None = None
    typical_high: float | None = None


class PeriodHrvStats(DefaultsRequired):
    """HRV summary recomputed from raw overnight summaries across a period."""

    avg_nightly: float | None = None
    avg_weekly: float | None = None
    balanced_pct: float | None = None
    total_days: int = 0


class PeriodSpo2Stats(DefaultsRequired):
    """SpO2 summary recomputed from raw pulse-ox readings across a period."""

    avg: float | None = None
    lowest_min: float | None = None
    low_days: int = 0
    total_days: int = 0


class PeriodSkinTempStats(DefaultsRequired):
    """Skin-temperature summary recomputed from overnight rows across a period."""

    avg_deviation: float | None = None
    max_deviation: float | None = None
    min_deviation: float | None = None
    avg_nightly: float | None = None
    days_tracked: int = 0


class PeriodSleepStats(DefaultsRequired):
    """Sleep summary recomputed from sleep assessments across a period."""

    avg_score: float | None = None
    avg_deep_score: float | None = None
    days_tracked: int = 0


class PeriodBodyBatteryStats(DefaultsRequired):
    """Body Battery extrema summary recomputed across a period."""

    avg_min: float | None = None
    avg_max: float | None = None
    days_tracked: int = 0


class PeriodSummary(DefaultsRequired):
    """All metric summaries for one standard analytics window."""

    heart_rate: PeriodHeartRateStats
    stress: PeriodMetricStats
    respiration: PeriodMetricStats
    hrv: PeriodHrvStats
    spo2: PeriodSpo2Stats
    skin_temp: PeriodSkinTempStats
    sleep: PeriodSleepStats
    body_battery: PeriodBodyBatteryStats


class DailyAggregatesResponse(DefaultsRequired):
    """Daily metric mart plus standard period-window summaries."""

    days: list[str]
    daily: list[DailyMetric]
    period_windows: dict[str, PeriodSummary] = {}


class HeartRateDailyPoint(DefaultsRequired):
    """Heart-rate daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    heart_rate: DailyHeartRateStats


class HeartRateDailyResponse(DefaultsRequired):
    """Daily heart-rate metrics plus heart-rate period summaries."""

    days: list[str]
    daily: list[HeartRateDailyPoint]
    period_windows: dict[str, PeriodHeartRateStats] = {}


class HrvDailyPoint(DefaultsRequired):
    """HRV daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    hrv: DailyHrvStats


class HrvDailyResponse(DefaultsRequired):
    """Daily HRV metrics plus HRV period summaries."""

    days: list[str]
    daily: list[HrvDailyPoint]
    period_windows: dict[str, PeriodHrvStats] = {}


class SleepDailyPoint(DefaultsRequired):
    """Sleep daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    sleep: DailySleepStats


class SleepDailyResponse(DefaultsRequired):
    """Daily sleep metrics plus sleep period summaries."""

    days: list[str]
    daily: list[SleepDailyPoint]
    period_windows: dict[str, PeriodSleepStats] = {}


class StressDailyPoint(DefaultsRequired):
    """Stress daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    stress: DailyMetricStats


class StressDailyResponse(DefaultsRequired):
    """Daily stress metrics plus stress period summaries."""

    days: list[str]
    daily: list[StressDailyPoint]
    period_windows: dict[str, PeriodMetricStats] = {}


class RespirationDailyPoint(DefaultsRequired):
    """Respiration daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    respiration: DailyMetricStats


class RespirationDailyResponse(DefaultsRequired):
    """Daily respiration metrics plus respiration period summaries."""

    days: list[str]
    daily: list[RespirationDailyPoint]
    period_windows: dict[str, PeriodMetricStats] = {}


class SpO2DailyPoint(DefaultsRequired):
    """Pulse-ox daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    spo2: DailyMetricStats


class SpO2DailyResponse(DefaultsRequired):
    """Daily pulse-ox metrics plus pulse-ox period summaries."""

    days: list[str]
    daily: list[SpO2DailyPoint]
    period_windows: dict[str, PeriodSpo2Stats] = {}


class SkinTempDailyPoint(DefaultsRequired):
    """Skin-temperature daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    skin_temp: DailySkinTempStats


class SkinTempDailyResponse(DefaultsRequired):
    """Daily skin-temperature metrics plus skin-temperature period summaries."""

    days: list[str]
    daily: list[SkinTempDailyPoint]
    period_windows: dict[str, PeriodSkinTempStats] = {}


class BodyBatteryDailyPoint(DefaultsRequired):
    """Body Battery daily metric row for metric-scoped endpoints."""

    date: str
    utc_offset_hours: float | None = None
    body_battery: DailyBodyBatteryStats


class BodyBatteryDailyResponse(DefaultsRequired):
    """Daily Body Battery metrics plus Body Battery period summaries."""

    days: list[str]
    daily: list[BodyBatteryDailyPoint]
    period_windows: dict[str, PeriodBodyBatteryStats] = {}
