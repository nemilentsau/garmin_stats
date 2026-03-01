"""Tests for parser extractor edge cases."""

from datetime import UTC, datetime

from app.models import (
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvValue,
    SkinTempOvernight,
    SleepLevel,
)
from app.parser import (
    _GARMIN_EPOCH_UNIX,
    _extract_hrv,
    _extract_utc_offset_hours,
    _extract_wellness,
    _shift_timestamps,
)


class TestExtractorZeroValues:
    def test_wellness_keeps_zero_heart_rate_steps_and_spo2(self):
        messages = {
            "monitoring_mesgs": [
                {"heart_rate": 0, "steps": 0},
            ],
            "spo2_data_mesgs": [
                {"reading_spo2": 0, "mode": "sleep"},
            ],
        }

        day = _extract_wellness(messages, "2026-01-15")
        assert [r.value for r in day.heart_rate] == [0]
        assert [r.steps for r in day.steps_summary] == [0]
        assert [r.value for r in day.spo2] == [0]

    def test_hrv_keeps_zero_value(self):
        messages = {
            "hrv_value_mesgs": [
                {"value": 0},
            ],
        }
        day = _extract_hrv(messages, "2026-01-15")
        assert [r.value for r in day.hrv_values] == [0]


# ---------------------------------------------------------------------------
# UTC offset extraction
# ---------------------------------------------------------------------------

def _make_monitoring_info(utc_dt: datetime, offset_hours: float) -> dict:
    """Build a monitoring_info_mesgs entry with a known UTC/local pair."""
    local_unix = utc_dt.timestamp() + offset_hours * 3600
    local_garmin = int(local_unix) - _GARMIN_EPOCH_UNIX
    return {"timestamp": utc_dt, "local_timestamp": local_garmin}


class TestExtractUtcOffset:
    def test_positive_offset_extracted(self):
        """NZ +13 offset is correctly extracted."""
        utc = datetime(2026, 1, 15, 3, 0, 0, tzinfo=UTC)
        messages = {"monitoring_info_mesgs": [_make_monitoring_info(utc, 13.0)]}
        assert _extract_utc_offset_hours(messages) == 13.0

    def test_negative_offset_extracted(self):
        """NYC -5 offset is correctly extracted."""
        utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        messages = {"monitoring_info_mesgs": [_make_monitoring_info(utc, -5.0)]}
        assert _extract_utc_offset_hours(messages) == -5.0

    def test_returns_none_when_no_monitoring_info(self):
        messages: dict[str, list[dict[str, object]]] = {"monitoring_info_mesgs": []}
        assert _extract_utc_offset_hours(messages) is None

    def test_returns_none_when_key_missing(self):
        assert _extract_utc_offset_hours({}) is None


# ---------------------------------------------------------------------------
# Timestamp shifting
# ---------------------------------------------------------------------------

class TestShiftTimestamps:
    def test_shifts_all_reading_types(self):
        """All timestamp fields across wellness, sleep, hrv, skin_temp are shifted."""
        ts = "2026-01-15T00:00:00+00:00"
        day = DayData(
            date="2026-01-15",
            wellness=DayWellness(
                date="2026-01-15",
                heart_rate=[HeartRateReading(timestamp=ts, value=70)],
            ),
            sleep=DaySleep(
                date="2026-01-15",
                sleep_levels=[SleepLevel(date="2026-01-15", timestamp=ts, level="deep")],
            ),
            hrv=DayHrv(
                date="2026-01-15",
                hrv_values=[HrvValue(date="2026-01-15", timestamp=ts, value=50.0)],
            ),
            skin_temp=DaySkinTemp(
                date="2026-01-15",
                skin_temp_overnight=[SkinTempOvernight(date="2026-01-15", timestamp=ts)],
            ),
        )
        _shift_timestamps(day, 13.0)

        expected = "2026-01-15T13:00:00+00:00"
        assert day.wellness.heart_rate[0].timestamp == expected
        assert day.sleep.sleep_levels[0].timestamp == expected
        assert day.hrv.hrv_values[0].timestamp == expected
        assert day.skin_temp.skin_temp_overnight[0].timestamp == expected

    def test_negative_offset_shifts_backwards(self):
        ts = "2026-01-15T03:00:00+00:00"
        day = DayData(
            date="2026-01-15",
            wellness=DayWellness(
                date="2026-01-15",
                heart_rate=[HeartRateReading(timestamp=ts, value=60)],
            ),
            sleep=DaySleep(date="2026-01-15"),
            hrv=DayHrv(date="2026-01-15"),
            skin_temp=DaySkinTemp(date="2026-01-15"),
        )
        _shift_timestamps(day, -5.0)
        assert day.wellness.heart_rate[0].timestamp == "2026-01-14T22:00:00+00:00"

    def test_none_timestamps_preserved(self):
        day = DayData(
            date="2026-01-15",
            wellness=DayWellness(
                date="2026-01-15",
                heart_rate=[HeartRateReading(timestamp=None, value=60)],
            ),
            sleep=DaySleep(date="2026-01-15"),
            hrv=DayHrv(date="2026-01-15"),
            skin_temp=DaySkinTemp(date="2026-01-15"),
        )
        _shift_timestamps(day, 5.0)
        assert day.wellness.heart_rate[0].timestamp is None
