"""Period-window Garmin summary contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetricStats,
    DailySleepStats,
    HRZoneBucket,
)


class DailySkinTempDisplayStats(DefaultsRequired):
    """Display-ready daily skin-temperature values in Fahrenheit."""

    deviation_f: float | None = None
    deviation_7_day_f: float | None = None
    nightly_value_f: float | None = None


class DailyMetricDisplay(DefaultsRequired):
    """Public daily metric row with display-ready skin temperature."""

    date: str
    utc_offset_hours: float | None = None
    heart_rate: DailyHeartRateStats
    stress: DailyMetricStats
    body_battery: DailyBodyBatteryStats
    spo2: DailyMetricStats
    respiration: DailyMetricStats
    hrv: DailyHrvStats
    sleep: DailySleepStats
    skin_temp: DailySkinTempDisplayStats


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

    avg_deviation_f: float | None = None
    max_deviation_f: float | None = None
    min_deviation_f: float | None = None
    avg_nightly_f: float | None = None
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
    daily: list[DailyMetricDisplay]
    period_windows: dict[str, PeriodSummary] = {}


class HeartRateDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    heart_rate: DailyHeartRateStats


class HeartRateDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[HeartRateDailyPoint]
    period_windows: dict[str, PeriodHeartRateStats] = {}


class HrvDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    hrv: DailyHrvStats


class HrvDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[HrvDailyPoint]
    period_windows: dict[str, PeriodHrvStats] = {}


class SleepDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    sleep: DailySleepStats


class SleepDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[SleepDailyPoint]
    period_windows: dict[str, PeriodSleepStats] = {}


class StressDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    stress: DailyMetricStats


class StressDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[StressDailyPoint]
    period_windows: dict[str, PeriodMetricStats] = {}


class RespirationDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    respiration: DailyMetricStats


class RespirationDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[RespirationDailyPoint]
    period_windows: dict[str, PeriodMetricStats] = {}


class SpO2DailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    spo2: DailyMetricStats


class SpO2DailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[SpO2DailyPoint]
    period_windows: dict[str, PeriodSpo2Stats] = {}


class SkinTempDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    skin_temp: DailySkinTempDisplayStats


class SkinTempDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[SkinTempDailyPoint]
    period_windows: dict[str, PeriodSkinTempStats] = {}


class BodyBatteryDailyPoint(DefaultsRequired):
    date: str
    utc_offset_hours: float | None = None
    body_battery: DailyBodyBatteryStats


class BodyBatteryDailyResponse(DefaultsRequired):
    days: list[str]
    daily: list[BodyBatteryDailyPoint]
    period_windows: dict[str, PeriodBodyBatteryStats] = {}
