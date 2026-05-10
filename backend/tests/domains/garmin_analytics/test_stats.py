"""Tests for Garmin analytics aggregation, flattening, and period summaries."""

from app.domains.garmin_analytics.domain.aggregates.biometric_responses import (
    flatten_body_battery,
    flatten_heart_rate,
    flatten_respiration,
    flatten_spo2,
    flatten_stress,
)
from app.domains.garmin_analytics.domain.aggregates.period import (
    compute_period_summary,
)
from app.domains.garmin_health.contracts import (
    BodyBatteryReading,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    HrvSummary,
    RespirationReading,
    RestingHRReading,
    SkinTempOvernight,
    SleepAssessment,
    SpO2Reading,
    StressReading,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_day(
    date: str = "2026-01-15",
    hr_values: list[int] | None = None,
    stress_values: list[int] | None = None,
    spo2_values: list[int] | None = None,
    resp_values: list[float] | None = None,
    bb_values: list[int] | None = None,
    resting_hr: int | None = 48,
    current_day_resting_hr: int | None = None,
    sleep_score: int | None = 85,
    hrv_nightly: float | None = 55.0,
    hrv_weekly: float | None = 52.0,
    hrv_status: str = "balanced",
    skin_dev: float | None = 0.1,
    utc_offset_hours: float | None = None,
) -> DayData:
    """Build a DayData with controlled values for testing."""
    hr = [60, 70, 80, 90, 100] if hr_values is None else hr_values
    stress = [20, 30, 40] if stress_values is None else stress_values
    spo2 = [95, 96, 97] if spo2_values is None else spo2_values
    resp = [12.0, 14.0, 16.0] if resp_values is None else resp_values
    bb = [50, 60, 70] if bb_values is None else bb_values

    ts = "2026-01-15T{:02d}:00:00"
    wellness = DayWellness(
        date=date,
        heart_rate=[
            HeartRateReading(timestamp=ts.format(i), value=v)
            for i, v in enumerate(hr)
        ],
        stress=[
            StressReading(timestamp=ts.format(i), value=v)
            for i, v in enumerate(stress)
        ],
        body_battery=[
            BodyBatteryReading(timestamp=ts.format(i), value=v)
            for i, v in enumerate(bb)
        ],
        spo2=[
            SpO2Reading(timestamp=ts.format(i), value=v, mode="sleep")
            for i, v in enumerate(spo2)
        ],
        respiration=[
            RespirationReading(timestamp=ts.format(i), value=v)
            for i, v in enumerate(resp)
        ],
        resting_hr=[
            RestingHRReading(
                timestamp="2026-01-15T06:00:00",
                resting_hr=resting_hr,
                current_day_resting_hr=current_day_resting_hr,
            ),
        ] if resting_hr or current_day_resting_hr else [],
    )
    sleep = DaySleep(
        date=date,
        sleep_assessments=[SleepAssessment(
            date=date, overall_score=sleep_score, deep_sleep_score=70, rem_sleep_score=60,
        )] if sleep_score else [],
    )
    hrv = DayHrv(
        date=date,
        hrv_summaries=[HrvSummary(
            date=date, last_night_average=hrv_nightly, weekly_average=hrv_weekly, status=hrv_status,
        )] if hrv_nightly else [],
    )
    skin_temp = DaySkinTemp(
        date=date,
        skin_temp_overnight=[SkinTempOvernight(
            date=date, average_deviation=skin_dev, nightly_value=36.5,
        )] if skin_dev is not None else [],
    )
    return DayData(
        date=date, utc_offset_hours=utc_offset_hours,
        wellness=wellness, sleep=sleep, hrv=hrv, skin_temp=skin_temp,
    )


# ---------------------------------------------------------------------------
# compute_period_summary
# ---------------------------------------------------------------------------

class TestPeriodSummary:
    def test_period_avg_from_raw_readings_not_daily_averages(self):
        """Period avg should be from ALL readings, not average of daily averages."""
        # Day 1: 5 readings of 60
        # Day 2: 1 reading of 100
        # Average of averages: (60 + 100) / 2 = 80
        # True average: (60*5 + 100*1) / 6 = 66.7
        day1 = _make_day(date="2026-01-01", hr_values=[60, 60, 60, 60, 60])
        day2 = _make_day(date="2026-01-02", hr_values=[100])
        period = compute_period_summary([day1, day2])
        assert period.heart_rate.avg == 66.7  # NOT 80.0

    def test_resting_hr_averaged_across_days(self):
        day1 = _make_day(date="2026-01-01", resting_hr=45)
        day2 = _make_day(date="2026-01-02", resting_hr=50)
        period = compute_period_summary([day1, day2])
        assert period.heart_rate.avg_resting == 47.5

    def test_hrv_balanced_pct_rounded(self):
        day1 = _make_day(date="2026-01-01", hrv_status="balanced")
        day2 = _make_day(date="2026-01-02", hrv_status="low")
        day3 = _make_day(date="2026-01-03", hrv_status="balanced")
        period = compute_period_summary([day1, day2, day3])
        assert period.hrv.balanced_pct == 67  # 2/3 rounded
        assert period.hrv.total_days == 3

    def test_spo2_day_with_min_below_90_counted_as_low(self):
        day1 = _make_day(date="2026-01-01", spo2_values=[95, 96])
        day2 = _make_day(date="2026-01-02", spo2_values=[85, 88])  # min=85 < 90
        period = compute_period_summary([day1, day2])
        assert period.spo2.low_days == 1
        assert period.spo2.lowest_min == 85.0
        assert period.spo2.total_days == 2

    def test_spo2_89_is_low_90_is_not(self):
        """Boundary: m < 90 means 89 is low but 90 is not."""
        day_89 = _make_day(date="2026-01-01", spo2_values=[89])
        day_90 = _make_day(date="2026-01-02", spo2_values=[90])
        period = compute_period_summary([day_89, day_90])
        assert period.spo2.low_days == 1  # only day with min=89

    def test_skin_temp_min_max_deviation(self):
        day1 = _make_day(date="2026-01-01", skin_dev=-0.3)
        day2 = _make_day(date="2026-01-02", skin_dev=0.5)
        period = compute_period_summary([day1, day2])
        assert period.skin_temp.min_deviation == -0.3
        assert period.skin_temp.max_deviation == 0.5
        assert period.skin_temp.days_tracked == 2

    def test_all_none_when_no_days(self):
        period = compute_period_summary([])
        assert period.heart_rate.avg is None
        assert period.hrv.total_days == 0
        assert period.spo2.total_days == 0


# ---------------------------------------------------------------------------
# raw wellness metric projections
# ---------------------------------------------------------------------------

class TestFlattenWellnessMetricResponses:
    def test_heart_rate_response_contains_only_days_heart_rate_and_resting_hr(self):
        day1 = _make_day(date="2026-01-01", hr_values=[60, 70])
        day2 = _make_day(date="2026-01-02", hr_values=[80])

        resp = flatten_heart_rate([day1.wellness, day2.wellness])

        assert resp.days == ["2026-01-01", "2026-01-02"]
        assert [reading.value for reading in resp.heart_rate] == [60, 70, 80]
        assert [reading.resting_hr for reading in resp.resting_hr] == [48, 48]
        assert not hasattr(resp, "stress")

    def test_stress_response_contains_only_days_and_stress(self):
        day = _make_day(date="2026-01-01", stress_values=[20, 30])

        resp = flatten_stress([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.stress] == [20, 30]
        assert not hasattr(resp, "heart_rate")

    def test_body_battery_response_contains_only_days_and_body_battery(self):
        day = _make_day(date="2026-01-01", bb_values=[40, 80])

        resp = flatten_body_battery([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.body_battery] == [40, 80]
        assert not hasattr(resp, "stress")

    def test_spo2_response_contains_only_days_and_spo2(self):
        day = _make_day(date="2026-01-01", spo2_values=[95, 96])

        resp = flatten_spo2([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.spo2] == [95, 96]
        assert not hasattr(resp, "respiration")

    def test_respiration_response_contains_only_days_and_respiration(self):
        day = _make_day(date="2026-01-01", resp_values=[12.0, 13.0])

        resp = flatten_respiration([day.wellness])

        assert resp.days == ["2026-01-01"]
        assert [reading.value for reading in resp.respiration] == [12.0, 13.0]
        assert not hasattr(resp, "spo2")

    def test_metric_response_returns_empty_lists_for_no_days(self):
        resp = flatten_heart_rate([])

        assert resp.days == []
        assert resp.heart_rate == []
        assert resp.resting_hr == []
