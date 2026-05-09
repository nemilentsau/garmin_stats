"""Period-window Garmin aggregate stat contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import DailyMetric, HRZoneBucket


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
