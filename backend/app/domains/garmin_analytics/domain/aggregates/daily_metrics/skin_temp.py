"""Skin-temperature daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailySkinTempStats, DaySkinTemp


def compute_daily_skin_temp(skin_temp: DaySkinTemp) -> DailySkinTempStats:
    reading = skin_temp.skin_temp_overnight[0] if skin_temp.skin_temp_overnight else None
    return DailySkinTempStats(
        deviation=reading.average_deviation if reading else None,
        deviation_7_day=reading.average_7_day_deviation if reading else None,
        nightly_value=reading.nightly_value if reading else None,
    )
