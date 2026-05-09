"""Canonical persisted Garmin daily metric contracts."""

from app.contracts.base import DefaultsRequired


class HRZoneBucket(DefaultsRequired):
    """Heart-rate zone count and percentage for a day or period."""

    label: str
    min_bpm: int
    max_bpm: int | None = None
    count: int
    pct: float


class DailyHeartRateStats(DefaultsRequired):
    """Persisted daily heart-rate summary derived from raw readings."""

    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    resting: int | None = None
    zones: list[HRZoneBucket] = []


class DailyMetricStats(DefaultsRequired):
    """Common nullable scalar stats for one daily Garmin metric."""

    avg: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyBodyBatteryStats(DefaultsRequired):
    """Persisted daily Body Battery summary with integer extrema."""

    avg: float | None = None
    min: int | None = None
    max: int | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class DailyHrvStats(DefaultsRequired):
    """Persisted daily HRV summary from Garmin overnight status data."""

    weekly_avg: float | None = None
    nightly_avg: float | None = None
    status: str | None = None


class DailySleepStats(DefaultsRequired):
    """Persisted daily sleep score summary from Garmin sleep assessment."""

    score: int | None = None
    deep_score: int | None = None
    rem_score: int | None = None


class DailySkinTempStats(DefaultsRequired):
    """Persisted overnight skin-temperature deviation summary."""

    deviation: float | None = None
    deviation_7_day: float | None = None
    nightly_value: float | None = None


class DailyMetric(DefaultsRequired):
    """Canonical persisted Garmin health row for one local date."""

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
