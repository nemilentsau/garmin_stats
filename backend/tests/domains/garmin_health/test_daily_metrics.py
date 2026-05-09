"""Tests for canonical Garmin daily metric composition."""

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
from app.domains.garmin_health.domain.daily import compute_daily_metric
from app.domains.garmin_health.domain.daily_metrics import compute_hr_zones


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

    timestamp = "2026-01-15T{:02d}:00:00"
    wellness = DayWellness(
        date=date,
        heart_rate=[
            HeartRateReading(timestamp=timestamp.format(i), value=value)
            for i, value in enumerate(hr)
        ],
        stress=[
            StressReading(timestamp=timestamp.format(i), value=value)
            for i, value in enumerate(stress)
        ],
        body_battery=[
            BodyBatteryReading(timestamp=timestamp.format(i), value=value)
            for i, value in enumerate(bb)
        ],
        spo2=[
            SpO2Reading(timestamp=timestamp.format(i), value=value, mode="sleep")
            for i, value in enumerate(spo2)
        ],
        respiration=[
            RespirationReading(timestamp=timestamp.format(i), value=value)
            for i, value in enumerate(resp)
        ],
        resting_hr=[
            RestingHRReading(
                timestamp="2026-01-15T06:00:00",
                resting_hr=resting_hr,
                current_day_resting_hr=current_day_resting_hr,
            ),
        ]
        if resting_hr or current_day_resting_hr
        else [],
    )
    sleep = DaySleep(
        date=date,
        sleep_assessments=[
            SleepAssessment(
                date=date,
                overall_score=sleep_score,
                deep_sleep_score=70,
                rem_sleep_score=60,
            ),
        ]
        if sleep_score
        else [],
    )
    hrv = DayHrv(
        date=date,
        hrv_summaries=[
            HrvSummary(
                date=date,
                last_night_average=hrv_nightly,
                weekly_average=hrv_weekly,
                status=hrv_status,
            ),
        ]
        if hrv_nightly
        else [],
    )
    skin_temp = DaySkinTemp(
        date=date,
        skin_temp_overnight=[
            SkinTempOvernight(
                date=date,
                average_deviation=skin_dev,
                nightly_value=36.5,
            ),
        ]
        if skin_dev is not None
        else [],
    )
    return DayData(
        date=date,
        utc_offset_hours=utc_offset_hours,
        wellness=wellness,
        sleep=sleep,
        hrv=hrv,
        skin_temp=skin_temp,
    )


class TestDailyMetricComposition:
    def test_daily_hr_computes_avg_min_max_from_readings(self):
        day = _make_day(hr_values=[60, 70, 80, 90, 100])
        metric = compute_daily_metric(day)
        assert metric.heart_rate.avg == 80.0
        assert metric.heart_rate.min == 60
        assert metric.heart_rate.max == 100
        assert metric.heart_rate.median == 80.0
        assert metric.heart_rate.resting == 48

    def test_daily_stress_computes_avg_min_max_from_readings(self):
        day = _make_day(stress_values=[20, 30, 40])
        metric = compute_daily_metric(day)
        assert metric.stress.avg == 30.0
        assert metric.stress.min == 20
        assert metric.stress.max == 40

    def test_all_metrics_none_when_readings_empty(self):
        day = _make_day(
            hr_values=[],
            stress_values=[],
            spo2_values=[],
            resp_values=[],
            bb_values=[],
            resting_hr=None,
            sleep_score=None,
            hrv_nightly=None,
            skin_dev=None,
        )
        metric = compute_daily_metric(day)
        assert metric.heart_rate.avg is None
        assert metric.heart_rate.min is None
        assert metric.stress.avg is None

    def test_sleep_score_extracted_from_first_assessment(self):
        day = _make_day(sleep_score=85)
        metric = compute_daily_metric(day)
        assert metric.sleep.score == 85
        assert metric.sleep.deep_score == 70
        assert metric.sleep.rem_score == 60

    def test_sleep_none_when_no_assessments(self):
        day = _make_day(sleep_score=None)
        metric = compute_daily_metric(day)
        assert metric.sleep.score is None

    def test_hrv_extracted_from_first_summary(self):
        day = _make_day(hrv_nightly=55.0, hrv_weekly=52.0)
        metric = compute_daily_metric(day)
        assert metric.hrv.nightly_avg == 55.0
        assert metric.hrv.weekly_avg == 52.0
        assert metric.hrv.status == "Balanced"

    def test_skin_temp_extracted_from_first_overnight(self):
        day = _make_day(skin_dev=0.1)
        metric = compute_daily_metric(day)
        assert metric.skin_temp.deviation == 0.1
        assert metric.skin_temp.nightly_value == 36.5

    def test_current_day_resting_hr_takes_precedence(self):
        day = _make_day(resting_hr=50, current_day_resting_hr=45)
        metric = compute_daily_metric(day)
        assert metric.heart_rate.resting == 45

    def test_offset_propagated_to_daily_metric(self):
        day = _make_day(utc_offset_hours=13.0)
        metric = compute_daily_metric(day)
        assert metric.utc_offset_hours == 13.0

    def test_offset_none_when_not_set(self):
        day = _make_day()
        metric = compute_daily_metric(day)
        assert metric.utc_offset_hours is None


class TestHRZones:
    def test_returns_empty_for_no_readings(self):
        assert compute_hr_zones([]) == []

    def test_all_readings_in_one_zone_returns_100pct(self):
        zones = compute_hr_zones([70, 75, 80])
        assert len(zones) == 1
        assert zones[0].label == "Light"
        assert zones[0].pct == 100
        assert zones[0].count == 3

    def test_readings_distributed_across_all_zones(self):
        zones = compute_hr_zones([50, 55, 70, 90, 110, 140])
        by_label = {zone.label: zone for zone in zones}
        assert by_label["Rest"].count == 2
        assert by_label["Rest"].pct == 33
        assert by_label["Light"].count == 2
        assert by_label["Moderate"].count == 1
        assert by_label["Vigorous"].count == 1

    def test_at_boundary_values_fall_into_upper_zone(self):
        zones = compute_hr_zones([60, 100, 130])
        by_label = {zone.label: zone for zone in zones}
        assert "Rest" not in by_label
        assert by_label["Light"].count == 1
        assert by_label["Moderate"].count == 1
        assert by_label["Vigorous"].count == 1

    def test_below_boundary_values_fall_into_lower_zone(self):
        zones = compute_hr_zones([59, 99, 129])
        by_label = {zone.label: zone for zone in zones}
        assert "Vigorous" not in by_label
        assert by_label["Rest"].count == 1
        assert by_label["Light"].count == 1
        assert by_label["Moderate"].count == 1

    def test_zones_aggregated_in_daily_metric(self):
        day = _make_day(hr_values=[50, 70, 110, 140])
        metric = compute_daily_metric(day)
        assert len(metric.heart_rate.zones) > 0
        total_count = sum(zone.count for zone in metric.heart_rate.zones)
        assert total_count == 4

    def test_zone_bucket_exposes_min_max_bpm(self):
        zones = compute_hr_zones([50, 140])
        rest = next(zone for zone in zones if zone.label == "Rest")
        assert rest.min_bpm == 0
        assert rest.max_bpm == 60
        vigorous = next(zone for zone in zones if zone.label == "Vigorous")
        assert vigorous.min_bpm == 130
        assert vigorous.max_bpm is None
