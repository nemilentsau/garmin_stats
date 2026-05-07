"""Tests for Garmin analytics aggregation, flattening, and period summaries."""

from app.domains.garmin_analytics.contracts import (
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
from app.domains.garmin_analytics.domain.aggregates.biometric_responses import (
    flatten_wellness,
)
from app.domains.garmin_analytics.domain.aggregates.daily import (
    aggregate_day,
    compute_hr_zones,
)
from app.domains.garmin_analytics.domain.aggregates.period import (
    compute_period_summary,
)
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_median,
    safe_percentile,
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
# safe_avg / safe_median / safe_percentile
# ---------------------------------------------------------------------------

class TestSafeHelpers:
    def test_avg_returns_rounded_mean_for_nonempty_list(self):
        assert safe_avg([10, 20, 30]) == 20.0

    def test_avg_returns_none_for_empty_list(self):
        assert safe_avg([]) is None

    def test_median_returns_middle_value(self):
        assert safe_median([1, 3, 2]) == 2.0

    def test_median_returns_none_for_empty_list(self):
        assert safe_median([]) is None

    def test_percentile_returns_interpolated_value(self):
        vals = list(range(1, 101))  # 1..100
        assert safe_percentile(vals, 25) == 25.8

    def test_percentile_returns_none_for_empty_list(self):
        assert safe_percentile([], 50) is None


# ---------------------------------------------------------------------------
# aggregate_day
# ---------------------------------------------------------------------------

class TestAggregateDay:
    def test_daily_hr_computes_avg_min_max_from_readings(self):
        day = _make_day(hr_values=[60, 70, 80, 90, 100])
        agg = aggregate_day(day)
        assert agg.heart_rate.avg == 80.0
        assert agg.heart_rate.min == 60
        assert agg.heart_rate.max == 100
        assert agg.heart_rate.median == 80.0
        assert agg.heart_rate.resting == 48

    def test_daily_stress_computes_avg_min_max_from_readings(self):
        day = _make_day(stress_values=[20, 30, 40])
        agg = aggregate_day(day)
        assert agg.stress.avg == 30.0
        assert agg.stress.min == 20
        assert agg.stress.max == 40

    def test_all_metrics_none_when_readings_empty(self):
        day = _make_day(
            hr_values=[], stress_values=[], spo2_values=[],
            resp_values=[], bb_values=[], resting_hr=None,
            sleep_score=None, hrv_nightly=None, skin_dev=None,
        )
        agg = aggregate_day(day)
        assert agg.heart_rate.avg is None
        assert agg.heart_rate.min is None
        assert agg.stress.avg is None

    def test_sleep_score_extracted_from_first_assessment(self):
        day = _make_day(sleep_score=85)
        agg = aggregate_day(day)
        assert agg.sleep.score == 85
        assert agg.sleep.deep_score == 70
        assert agg.sleep.rem_score == 60

    def test_sleep_none_when_no_assessments(self):
        day = _make_day(sleep_score=None)
        agg = aggregate_day(day)
        assert agg.sleep.score is None

    def test_hrv_extracted_from_first_summary(self):
        day = _make_day(hrv_nightly=55.0, hrv_weekly=52.0)
        agg = aggregate_day(day)
        assert agg.hrv.nightly_avg == 55.0
        assert agg.hrv.weekly_avg == 52.0
        assert agg.hrv.status == "Balanced"

    def test_skin_temp_extracted_from_first_overnight(self):
        day = _make_day(skin_dev=0.1)
        agg = aggregate_day(day)
        assert agg.skin_temp.deviation == 0.1
        assert agg.skin_temp.nightly_value == 36.5

    def test_current_day_resting_hr_takes_precedence(self):
        """current_day_resting_hr should be preferred over resting_hr."""
        day = _make_day(resting_hr=50, current_day_resting_hr=45)
        agg = aggregate_day(day)
        assert agg.heart_rate.resting == 45

    def test_offset_propagated_to_daily_metric(self):
        day = _make_day(utc_offset_hours=13.0)
        agg = aggregate_day(day)
        assert agg.utc_offset_hours == 13.0

    def test_offset_none_when_not_set(self):
        day = _make_day()
        agg = aggregate_day(day)
        assert agg.utc_offset_hours is None


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
# compute_hr_zones
# ---------------------------------------------------------------------------

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
        # 2 rest (<60), 2 light (60-99), 1 moderate (100-129), 1 vigorous (130+)
        zones = compute_hr_zones([50, 55, 70, 90, 110, 140])
        by_label = {z.label: z for z in zones}
        assert by_label["Rest"].count == 2
        assert by_label["Rest"].pct == 33  # 2/6 ~ 33%
        assert by_label["Light"].count == 2
        assert by_label["Moderate"].count == 1
        assert by_label["Vigorous"].count == 1

    def test_at_boundary_values_fall_into_upper_zone(self):
        """60 -> Light (not Rest), 100 -> Moderate (not Light), 130 -> Vigorous."""
        zones = compute_hr_zones([60, 100, 130])
        by_label = {z.label: z for z in zones}
        assert "Rest" not in by_label
        assert by_label["Light"].count == 1
        assert by_label["Moderate"].count == 1
        assert by_label["Vigorous"].count == 1

    def test_below_boundary_values_fall_into_lower_zone(self):
        """59 -> Rest, 99 -> Light, 129 -> Moderate."""
        zones = compute_hr_zones([59, 99, 129])
        by_label = {z.label: z for z in zones}
        assert "Vigorous" not in by_label
        assert by_label["Rest"].count == 1
        assert by_label["Light"].count == 1
        assert by_label["Moderate"].count == 1

    def test_zones_aggregated_in_daily_metric(self):
        day = _make_day(hr_values=[50, 70, 110, 140])
        agg = aggregate_day(day)
        assert len(agg.heart_rate.zones) > 0
        total_count = sum(z.count for z in agg.heart_rate.zones)
        assert total_count == 4

    def test_zones_aggregated_in_period_summary(self):
        day1 = _make_day(date="2026-01-01", hr_values=[50, 70])
        day2 = _make_day(date="2026-01-02", hr_values=[110, 140])
        period = compute_period_summary([day1, day2])
        assert len(period.heart_rate.zones) > 0
        total_count = sum(z.count for z in period.heart_rate.zones)
        assert total_count == 4

    def test_zone_bucket_exposes_min_max_bpm(self):
        zones = compute_hr_zones([50, 140])
        rest = next(z for z in zones if z.label == "Rest")
        assert rest.min_bpm == 0
        assert rest.max_bpm == 60
        vigorous = next(z for z in zones if z.label == "Vigorous")
        assert vigorous.min_bpm == 130
        assert vigorous.max_bpm is None


# ---------------------------------------------------------------------------
# flatten_wellness
# ---------------------------------------------------------------------------

class TestFlattenWellness:
    def test_concatenates_readings_across_days(self):
        day1 = _make_day(date="2026-01-01", hr_values=[60, 70])
        day2 = _make_day(date="2026-01-02", hr_values=[80])
        resp = flatten_wellness([day1.wellness, day2.wellness])
        assert resp.days == ["2026-01-01", "2026-01-02"]
        assert len(resp.heart_rate) == 3  # 2 + 1

    def test_returns_empty_lists_for_no_days(self):
        resp = flatten_wellness([])
        assert resp.days == []
        assert resp.heart_rate == []
