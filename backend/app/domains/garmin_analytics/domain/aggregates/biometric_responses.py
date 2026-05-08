"""Raw biometric response shaping for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    BodyBatteryRawResponse,
    BodyBatteryReading,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateRawResponse,
    HeartRateReading,
    HrvResponse,
    RespirationRawResponse,
    RespirationReading,
    RestingHRReading,
    SkinTempResponse,
    SleepResponse,
    SpO2RawResponse,
    SpO2Reading,
    StressRawResponse,
    StressReading,
)


def flatten_heart_rate(days: list[DayWellness]) -> HeartRateRawResponse:
    heart_rate: list[HeartRateReading] = []
    resting_hr: list[RestingHRReading] = []
    for day in days:
        heart_rate.extend(day.heart_rate)
        resting_hr.extend(day.resting_hr)
    return HeartRateRawResponse(
        days=[day.date for day in days],
        heart_rate=heart_rate,
        resting_hr=resting_hr,
    )


def flatten_stress(days: list[DayWellness]) -> StressRawResponse:
    stress: list[StressReading] = []
    for day in days:
        stress.extend(day.stress)
    return StressRawResponse(
        days=[day.date for day in days],
        stress=stress,
    )


def flatten_body_battery(days: list[DayWellness]) -> BodyBatteryRawResponse:
    body_battery: list[BodyBatteryReading] = []
    for day in days:
        body_battery.extend(day.body_battery)
    return BodyBatteryRawResponse(
        days=[day.date for day in days],
        body_battery=body_battery,
    )


def flatten_spo2(days: list[DayWellness]) -> SpO2RawResponse:
    spo2: list[SpO2Reading] = []
    for day in days:
        spo2.extend(day.spo2)
    return SpO2RawResponse(
        days=[day.date for day in days],
        spo2=spo2,
    )


def flatten_respiration(days: list[DayWellness]) -> RespirationRawResponse:
    respiration: list[RespirationReading] = []
    for day in days:
        respiration.extend(day.respiration)
    return RespirationRawResponse(
        days=[day.date for day in days],
        respiration=respiration,
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
