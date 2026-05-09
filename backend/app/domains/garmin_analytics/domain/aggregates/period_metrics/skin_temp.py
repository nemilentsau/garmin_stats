"""Skin-temperature raw-period aggregate calculations."""

from app.domains.garmin_analytics.contracts import DayData, PeriodSkinTempStats
from app.domains.garmin_analytics.domain.primitives.numeric import safe_avg


def compute_period_skin_temp(days: list[DayData]) -> PeriodSkinTempStats:
    deviations: list[float] = []
    nightly_values: list[float] = []
    for day in days:
        for reading in day.skin_temp.skin_temp_overnight:
            if reading.average_deviation is not None:
                deviations.append(reading.average_deviation)
            if reading.nightly_value is not None:
                nightly_values.append(reading.nightly_value)

    return PeriodSkinTempStats(
        avg_deviation=safe_avg(deviations),
        max_deviation=round(max(deviations), 2) if deviations else None,
        min_deviation=round(min(deviations), 2) if deviations else None,
        avg_nightly=safe_avg(nightly_values),
        days_tracked=len(deviations),
    )
