"""Skin-temperature period summary calculations from raw readings."""

from app.domains.garmin_analytics.contracts import PeriodSkinTempStats
from app.domains.garmin_health.contracts import DayData
from app.utils.units import c_delta_to_f_delta, c_to_f


def compute_period_skin_temp(days: list[DayData]) -> PeriodSkinTempStats:
    """Compute period skin-temperature stats from raw overnight rows."""
    deviations: list[float] = []
    nightly_values: list[float] = []
    for day in days:
        for reading in day.skin_temp.skin_temp_overnight:
            if reading.average_deviation is not None:
                deviations.append(reading.average_deviation)
            if reading.nightly_value is not None:
                nightly_values.append(reading.nightly_value)

    return PeriodSkinTempStats(
        avg_deviation_f=(
            c_delta_to_f_delta(sum(deviations) / len(deviations))
            if deviations
            else None
        ),
        max_deviation_f=c_delta_to_f_delta(max(deviations)) if deviations else None,
        min_deviation_f=c_delta_to_f_delta(min(deviations)) if deviations else None,
        avg_nightly_f=(
            c_to_f(sum(nightly_values) / len(nightly_values))
            if nightly_values
            else None
        ),
        days_tracked=len(deviations),
    )
