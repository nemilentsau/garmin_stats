"""Period aggregate read-model construction for Garmin analytics.

This module is only the window-level composer. Metric-specific raw-reading
policy lives in `period_metrics/`.
"""

from app.domains.garmin_analytics.contracts import PeriodSummary
from app.domains.garmin_analytics.domain.aggregates.period_metrics import (
    compute_period_body_battery,
    compute_period_heart_rate,
    compute_period_hrv,
    compute_period_respiration,
    compute_period_skin_temp,
    compute_period_sleep,
    compute_period_spo2,
    compute_period_stress,
)
from app.domains.garmin_health.contracts import DayData


def compute_period_summary(days: list[DayData]) -> PeriodSummary:
    """Compute period-level stats from raw per-day data (not from daily averages)."""
    return PeriodSummary(
        heart_rate=compute_period_heart_rate(days),
        stress=compute_period_stress(days),
        respiration=compute_period_respiration(days),
        hrv=compute_period_hrv(days),
        spo2=compute_period_spo2(days),
        skin_temp=compute_period_skin_temp(days),
        sleep=compute_period_sleep(days),
        body_battery=compute_period_body_battery(days),
    )
