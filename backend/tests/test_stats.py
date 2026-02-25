"""Tests for stats.py — aggregation, flattening, period summary."""

from app.models import (
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
from app.stats import (
    aggregate_day,
    compute_hr_zones,
    compute_period_summary,
    flatten_wellness,
    safe_avg,
    safe_median,
    safe_percentile,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestSafeHelpers:
    def test_safe_avg_nonempty(self):
        assert safe_avg([10, 20, 30]) == 20.0

    def test_safe_avg_empty(self):
        assert safe_avg([]) is None

    def test_safe_avg_single(self):
        assert safe_avg([42]) == 42.0

    def test_safe_avg_rounds(self):
        assert safe_avg([1, 2]) == 1.5

    def test_safe_median_nonempty(self):
        assert safe_median([1, 3, 2]) == 2.0

    def test_safe_median_empty(self):
        assert safe_median([]) is None

    def test_safe_percentile_q25(self):
        vals = list(range(1, 101))  # 1..100
        assert safe_percentile(vals, 25) == 25.8

    def test_safe_percentile_empty(self):
        assert safe_percentile([], 50) is None


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
    sleep_score: int | None = 85,
    hrv_nightly: float | None = 55.0,
    hrv_weekly: float | None = 52.0,
    hrv_status: str = "balanced",
    skin_dev: float | None = 0.1,
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
            ),
        ] if resting_hr else [],
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
    return DayData(date=date, wellness=wellness, sleep=sleep, hrv=hrv, skin_temp=skin_temp)


# ---------------------------------------------------------------------------
# aggregate_day
# ---------------------------------------------------------------------------

class TestAggregateDay:
    def test_heart_rate_stats(self):
        day = _make_day(hr_values=[60, 70, 80, 90, 100])
        agg = aggregate_day(day)
        assert agg.heart_rate.avg == 80.0
        assert agg.heart_rate.min == 60
        assert agg.heart_rate.max == 100
        assert agg.heart_rate.median == 80.0
        assert agg.heart_rate.resting == 48

    def test_stress_stats(self):
        day = _make_day(stress_values=[20, 30, 40])
        agg = aggregate_day(day)
        assert agg.stress.avg == 30.0
        assert agg.stress.min == 20
        assert agg.stress.max == 40

    def test_empty_readings(self):
        day = _make_day(
            hr_values=[], stress_values=[], spo2_values=[],
            resp_values=[], bb_values=[], resting_hr=None,
            sleep_score=None, hrv_nightly=None, skin_dev=None,
        )
        agg = aggregate_day(day)
        assert agg.heart_rate.avg is None
        assert agg.heart_rate.min is None
        assert agg.stress.avg is None

    def test_sleep_stats(self):
        day = _make_day(sleep_score=85)
        agg = aggregate_day(day)
        assert agg.sleep.score == 85
        assert agg.sleep.deep_score == 70
        assert agg.sleep.rem_score == 60

    def test_no_sleep_data(self):
        day = _make_day(sleep_score=None)
        agg = aggregate_day(day)
        assert agg.sleep.score is None

    def test_hrv_stats(self):
        day = _make_day(hrv_nightly=55.0, hrv_weekly=52.0)
        agg = aggregate_day(day)
        assert agg.hrv.nightly_avg == 55.0
        assert agg.hrv.weekly_avg == 52.0
        assert agg.hrv.status == "balanced"

    def test_skin_temp_stats(self):
        day = _make_day(skin_dev=0.1)
        agg = aggregate_day(day)
        assert agg.skin_temp.deviation == 0.1
        assert agg.skin_temp.nightly_value == 36.5


# ---------------------------------------------------------------------------
# compute_period_summary
# ---------------------------------------------------------------------------

class TestPeriodSummary:
    def test_hr_period_from_raw_data(self):
        """Period avg should be from ALL readings, not average of daily averages."""
        # Day 1: 5 readings of 60
        # Day 2: 1 reading of 100
        # Average of averages: (60 + 100) / 2 = 80
        # True average: (60*5 + 100*1) / 6 = 66.7
        day1 = _make_day(date="2026-01-01", hr_values=[60, 60, 60, 60, 60])
        day2 = _make_day(date="2026-01-02", hr_values=[100])
        period = compute_period_summary([day1, day2])
        assert period.heart_rate.avg == 66.7  # NOT 80.0

    def test_resting_hr_period(self):
        day1 = _make_day(date="2026-01-01", resting_hr=45)
        day2 = _make_day(date="2026-01-02", resting_hr=50)
        period = compute_period_summary([day1, day2])
        assert period.heart_rate.avg_resting == 47.5

    def test_hrv_balanced_pct(self):
        day1 = _make_day(date="2026-01-01", hrv_status="balanced")
        day2 = _make_day(date="2026-01-02", hrv_status="low")
        day3 = _make_day(date="2026-01-03", hrv_status="balanced")
        period = compute_period_summary([day1, day2, day3])
        assert period.hrv.balanced_pct == 67  # 2/3 rounded
        assert period.hrv.total_days == 3

    def test_spo2_low_days(self):
        day1 = _make_day(date="2026-01-01", spo2_values=[95, 96])
        day2 = _make_day(date="2026-01-02", spo2_values=[85, 88])  # min=85 < 90
        period = compute_period_summary([day1, day2])
        assert period.spo2.low_days == 1
        assert period.spo2.lowest_min == 85.0
        assert period.spo2.total_days == 2

    def test_skin_temp_extremes(self):
        day1 = _make_day(date="2026-01-01", skin_dev=-0.3)
        day2 = _make_day(date="2026-01-02", skin_dev=0.5)
        period = compute_period_summary([day1, day2])
        assert period.skin_temp.min_deviation == -0.3
        assert period.skin_temp.max_deviation == 0.5
        assert period.skin_temp.days_tracked == 2

    def test_empty_days(self):
        period = compute_period_summary([])
        assert period.heart_rate.avg is None
        assert period.hrv.total_days == 0
        assert period.spo2.total_days == 0


# ---------------------------------------------------------------------------
# compute_hr_zones
# ---------------------------------------------------------------------------

class TestHRZones:
    def test_empty_values(self):
        assert compute_hr_zones([]) == []

    def test_single_zone(self):
        zones = compute_hr_zones([70, 75, 80])
        assert len(zones) == 1
        assert zones[0].label == "Light"
        assert zones[0].pct == 100
        assert zones[0].count == 3

    def test_multi_zone_distribution(self):
        # 2 rest (<60), 2 light (60-99), 1 moderate (100-129), 1 vigorous (130+)
        zones = compute_hr_zones([50, 55, 70, 90, 110, 140])
        by_label = {z.label: z for z in zones}
        assert by_label["Rest"].count == 2
        assert by_label["Rest"].pct == 33  # 2/6 ≈ 33%
        assert by_label["Light"].count == 2
        assert by_label["Moderate"].count == 1
        assert by_label["Vigorous"].count == 1

    def test_boundary_values(self):
        """60 → Light (not Rest), 100 → Moderate (not Light), 130 → Vigorous."""
        zones = compute_hr_zones([60, 100, 130])
        by_label = {z.label: z for z in zones}
        assert "Rest" not in by_label
        assert by_label["Light"].count == 1
        assert by_label["Moderate"].count == 1
        assert by_label["Vigorous"].count == 1

    def test_zero_pct_zones_filtered(self):
        """Zones with 0 readings are excluded."""
        zones = compute_hr_zones([70, 75])  # all Light
        labels = [z.label for z in zones]
        assert labels == ["Light"]

    def test_zones_in_aggregate_day(self):
        day = _make_day(hr_values=[50, 70, 110, 140])
        agg = aggregate_day(day)
        assert len(agg.heart_rate.zones) > 0
        total_count = sum(z.count for z in agg.heart_rate.zones)
        assert total_count == 4

    def test_zones_in_period_summary(self):
        day1 = _make_day(date="2026-01-01", hr_values=[50, 70])
        day2 = _make_day(date="2026-01-02", hr_values=[110, 140])
        period = compute_period_summary([day1, day2])
        assert len(period.heart_rate.zones) > 0
        total_count = sum(z.count for z in period.heart_rate.zones)
        assert total_count == 4

    def test_zone_min_max_bpm(self):
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
    def test_flattens_multiple_days(self):
        day1 = _make_day(date="2026-01-01", hr_values=[60, 70])
        day2 = _make_day(date="2026-01-02", hr_values=[80])
        resp = flatten_wellness([day1.wellness, day2.wellness])
        assert resp.days == ["2026-01-01", "2026-01-02"]
        assert len(resp.heart_rate) == 3  # 2 + 1

    def test_flattens_empty(self):
        resp = flatten_wellness([])
        assert resp.days == []
        assert resp.heart_rate == []
