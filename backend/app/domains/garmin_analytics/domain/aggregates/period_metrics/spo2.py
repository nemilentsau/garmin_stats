"""SpO2 period summary calculations from raw readings."""

from app.domains.garmin_analytics.contracts import PeriodSpo2Stats
from app.domains.garmin_health.contracts import DayData
from app.utils.numeric import safe_avg


def compute_period_spo2(days: list[DayData]) -> PeriodSpo2Stats:
    """Compute period SpO2 stats from raw pulse-ox readings."""
    values = [r.value for day in days for r in day.wellness.spo2]
    day_mins: list[int] = []
    for day in days:
        day_values = [r.value for r in day.wellness.spo2]
        if day_values:
            day_mins.append(min(day_values))

    return PeriodSpo2Stats(
        avg=safe_avg(values),
        lowest_min=float(min(day_mins)) if day_mins else None,
        low_days=sum(1 for value in day_mins if value < 90),
        total_days=len(day_mins),
    )
