"""Raw biometric response shaping for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    ActivityReading,
    BodyBatteryReading,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvResponse,
    RespirationReading,
    RestingHRReading,
    SkinTempResponse,
    SleepResponse,
    SpO2Reading,
    StepsReading,
    StressReading,
    WellnessResponse,
)


def flatten_wellness(days: list[DayWellness]) -> WellnessResponse:
    dates: list[str] = []
    heart_rate: list[HeartRateReading] = []
    stress: list[StressReading] = []
    body_battery: list[BodyBatteryReading] = []
    spo2: list[SpO2Reading] = []
    respiration: list[RespirationReading] = []
    activity: list[ActivityReading] = []
    steps_summary: list[StepsReading] = []
    resting_hr: list[RestingHRReading] = []
    for d in days:
        dates.append(d.date)
        heart_rate.extend(d.heart_rate)
        stress.extend(d.stress)
        body_battery.extend(d.body_battery)
        spo2.extend(d.spo2)
        respiration.extend(d.respiration)
        activity.extend(d.activity)
        steps_summary.extend(d.steps_summary)
        resting_hr.extend(d.resting_hr)
    return WellnessResponse(
        days=dates,
        heart_rate=heart_rate,
        stress=stress,
        body_battery=body_battery,
        spo2=spo2,
        respiration=respiration,
        activity=activity,
        steps_summary=steps_summary,
        resting_hr=resting_hr,
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
