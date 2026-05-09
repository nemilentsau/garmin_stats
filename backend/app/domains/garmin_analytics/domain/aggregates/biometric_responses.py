"""Raw biometric response shaping for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    BodyBatteryRawResponse,
    HeartRateRawResponse,
    HrvResponse,
    RespirationRawResponse,
    SkinTempResponse,
    SleepResponse,
    SpO2RawResponse,
    StressRawResponse,
)
from app.domains.garmin_health.contracts import (
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
)


def flatten_heart_rate(days: list[DayWellness]) -> HeartRateRawResponse:
    return HeartRateRawResponse(
        days=[d.date for d in days],
        heart_rate=[r for d in days for r in d.heart_rate],
        resting_hr=[r for d in days for r in d.resting_hr],
    )


def flatten_stress(days: list[DayWellness]) -> StressRawResponse:
    return StressRawResponse(
        days=[d.date for d in days],
        stress=[r for d in days for r in d.stress],
    )


def flatten_body_battery(days: list[DayWellness]) -> BodyBatteryRawResponse:
    return BodyBatteryRawResponse(
        days=[d.date for d in days],
        body_battery=[r for d in days for r in d.body_battery],
    )


def flatten_spo2(days: list[DayWellness]) -> SpO2RawResponse:
    return SpO2RawResponse(
        days=[d.date for d in days],
        spo2=[r for d in days for r in d.spo2],
    )


def flatten_respiration(days: list[DayWellness]) -> RespirationRawResponse:
    return RespirationRawResponse(
        days=[d.date for d in days],
        respiration=[r for d in days for r in d.respiration],
    )


def flatten_sleep(days: list[DaySleep]) -> SleepResponse:
    return SleepResponse(
        days=[d.date for d in days],
        sleep_levels=[r for d in days for r in d.sleep_levels],
        sleep_assessments=[r for d in days for r in d.sleep_assessments],
    )


def flatten_hrv(days: list[DayHrv]) -> HrvResponse:
    return HrvResponse(
        days=[d.date for d in days],
        hrv_values=sorted(
            (r for d in days for r in d.hrv_values),
            key=lambda v: v.timestamp or "",
        ),
        hrv_summaries=[r for d in days for r in d.hrv_summaries],
    )


def flatten_skin_temp(days: list[DaySkinTemp]) -> SkinTempResponse:
    return SkinTempResponse(
        days=[d.date for d in days],
        skin_temp_overnight=[r for d in days for r in d.skin_temp_overnight],
    )
