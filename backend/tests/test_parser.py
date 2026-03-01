"""Tests for parser extractor edge cases."""

from app.parser import _extract_hrv, _extract_wellness


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
