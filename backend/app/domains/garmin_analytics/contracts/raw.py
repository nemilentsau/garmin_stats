"""Raw Garmin biometric endpoint response contracts."""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import (
    BodyBatteryReading,
    HeartRateReading,
    HrvSummary,
    HrvValue,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SleepLevel,
    SpO2Reading,
    StressReading,
)


class HeartRateRawResponse(DefaultsRequired):
    """Raw heart-rate endpoint response."""

    days: list[str]
    heart_rate: list[HeartRateReading]
    resting_hr: list[RestingHRReading]


class StressRawResponse(DefaultsRequired):
    """Raw stress endpoint response."""

    days: list[str]
    stress: list[StressReading]


class BodyBatteryRawResponse(DefaultsRequired):
    """Raw Body Battery endpoint response."""

    days: list[str]
    body_battery: list[BodyBatteryReading]


class SpO2RawResponse(DefaultsRequired):
    """Raw SpO2 endpoint response."""

    days: list[str]
    spo2: list[SpO2Reading]


class RespirationRawResponse(DefaultsRequired):
    """Raw respiration endpoint response."""

    days: list[str]
    respiration: list[RespirationReading]


class SleepResponse(DefaultsRequired):
    """Raw sleep endpoint response."""

    days: list[str]
    sleep_levels: list[SleepLevel]
    sleep_assessments: list[SleepAssessment]


class HrvResponse(DefaultsRequired):
    """Raw HRV endpoint response."""

    days: list[str]
    hrv_values: list[HrvValue]
    hrv_summaries: list[HrvSummary]


class SkinTempResponse(DefaultsRequired):
    """Raw skin-temperature endpoint response."""

    days: list[str]
    skin_temp_overnight: list[SkinTempOvernight]
