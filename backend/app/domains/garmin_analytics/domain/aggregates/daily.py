"""Daily aggregate read-model construction for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    DailyAggregatesResponse,
    DailyMetric,
    DayData,
)
from app.domains.garmin_analytics.domain.aggregates.daily_metrics import (
    HR_ZONE_THRESHOLDS,
    compute_daily_body_battery,
    compute_daily_heart_rate,
    compute_daily_hrv,
    compute_daily_respiration,
    compute_daily_skin_temp,
    compute_daily_sleep,
    compute_daily_spo2,
    compute_daily_stress,
    compute_hr_zones,
    is_balanced_hrv_status,
    is_unfavorable_hrv_status,
    normalize_hrv_status,
)

__all__ = [
    "HR_ZONE_THRESHOLDS",
    "aggregate_day",
    "compute_daily_aggregates",
    "compute_hr_zones",
    "is_balanced_hrv_status",
    "is_unfavorable_hrv_status",
    "normalize_hrv_status",
]


def aggregate_day(day: DayData) -> DailyMetric:
    """Compute aggregate stats for a single day."""
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


def compute_daily_aggregates(days: list[DayData]) -> DailyAggregatesResponse:
    """Compute daily aggregates for all days."""
    return DailyAggregatesResponse(
        days=[d.date for d in days],
        daily=[aggregate_day(d) for d in days],
    )
