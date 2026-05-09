"""Compose canonical persisted daily metric rows from parsed Garmin days."""

from app.domains.garmin_health.contracts import DailyMetric, DayData
from app.domains.garmin_health.domain.daily_metrics import (
    compute_daily_body_battery,
    compute_daily_heart_rate,
    compute_daily_hrv,
    compute_daily_respiration,
    compute_daily_skin_temp,
    compute_daily_sleep,
    compute_daily_spo2,
    compute_daily_stress,
)


def compute_daily_metric(day: DayData) -> DailyMetric:
    """Compute the persisted daily metric row for one parsed Garmin day."""
    return DailyMetric(
        date=day.date,
        utc_offset_hours=day.utc_offset_hours,
        heart_rate=compute_daily_heart_rate(day.wellness),
        stress=compute_daily_stress(day.wellness),
        body_battery=compute_daily_body_battery(day.wellness),
        spo2=compute_daily_spo2(day.wellness),
        respiration=compute_daily_respiration(day.wellness),
        hrv=compute_daily_hrv(day.hrv),
        sleep=compute_daily_sleep(day.sleep),
        skin_temp=compute_daily_skin_temp(day.skin_temp),
    )


def compute_daily_metrics(days: list[DayData]) -> list[DailyMetric]:
    """Compute persisted daily metric rows for parsed Garmin days."""
    return [compute_daily_metric(day) for day in days]
