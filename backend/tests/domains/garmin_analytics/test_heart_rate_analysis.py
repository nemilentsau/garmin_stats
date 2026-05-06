"""Tests for heart-rate analysis service compute functions."""

from app.domains.garmin_analytics.domain.analysis.heart_rate import (
    compute_circadian_profile,
    compute_hr_distribution,
    compute_resting_hr_trend,
    compute_sleeping_hr_trend,
    compute_weekly_resting_hr_boxplots,
)
from app.models import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DaySleep,
    DayWellness,
    HeartRateReading,
    SleepLevel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metric(date: str, resting: int | None) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, resting=resting),
        stress=DailyMetricStats(),
        body_battery=DailyBodyBatteryStats(),
        spo2=DailyMetricStats(),
        respiration=DailyMetricStats(),
        hrv=DailyHrvStats(),
        sleep=DailySleepStats(),
        skin_temp=DailySkinTempStats(),
    )


def _make_wellness(date: str, readings: list[HeartRateReading]) -> DayWellness:
    return DayWellness(date=date, heart_rate=readings)


def _make_sleep(date: str, levels: list[SleepLevel]) -> DaySleep:
    return DaySleep(date=date, sleep_levels=levels)


# ---------------------------------------------------------------------------
# Circadian profile
# ---------------------------------------------------------------------------

class TestCircadianProfile:
    def test_always_returns_24_points(self):
        result = compute_circadian_profile([])
        assert len(result) == 24
        assert all(p.avg_bpm is None for p in result)
        assert all(p.sample_count == 0 for p in result)

    def test_averages_by_hour(self):
        w = _make_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T08:00:00", value=60),
            HeartRateReading(timestamp="2026-01-15T08:30:00", value=80),
            HeartRateReading(timestamp="2026-01-15T12:00:00", value=100),
        ])
        result = compute_circadian_profile([w])
        hour_8 = result[8]
        assert hour_8.avg_bpm == 70.0
        assert hour_8.sample_count == 2
        assert result[12].avg_bpm == 100.0

    def test_zeros_excluded(self):
        w = _make_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T08:00:00", value=0),
            HeartRateReading(timestamp="2026-01-15T08:00:00", value=80),
        ])
        result = compute_circadian_profile([w])
        assert result[8].avg_bpm == 80.0
        assert result[8].sample_count == 1


# ---------------------------------------------------------------------------
# Sleeping HR trend
# ---------------------------------------------------------------------------

class TestSleepingHRTrend:
    def test_only_sleep_stage_readings_included(self):
        """Readings during 'awake' stage should be excluded."""
        sleep = _make_sleep("2026-01-15", [
            SleepLevel(date="2026-01-15", timestamp="2026-01-14T23:00:00", level="light"),
            SleepLevel(date="2026-01-15", timestamp="2026-01-15T01:00:00", level="awake"),
            SleepLevel(date="2026-01-15", timestamp="2026-01-15T01:30:00", level="deep"),
            SleepLevel(date="2026-01-15", timestamp="2026-01-15T03:00:00", level="rem"),
        ])
        w_prev = _make_wellness("2026-01-14", [
            HeartRateReading(timestamp="2026-01-14T23:30:00", value=55),  # light -> included
        ])
        w_curr = _make_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T01:15:00", value=100),  # awake -> excluded
            HeartRateReading(timestamp="2026-01-15T02:00:00", value=50),   # deep -> included
        ])
        result = compute_sleeping_hr_trend([w_prev, w_curr], [sleep])
        assert len(result) == 1
        assert result[0].date == "2026-01-15"
        # avg of 55 (light) + 50 (deep) = 52.5
        assert result[0].avg_sleeping_bpm == 52.5
        assert result[0].sample_count == 2

    def test_dates_without_sleep_data_skipped(self):
        w = _make_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T08:00:00", value=70),
        ])
        result = compute_sleeping_hr_trend([w], [])
        assert result == []

    def test_zero_hr_excluded(self):
        sleep = _make_sleep("2026-01-15", [
            SleepLevel(date="2026-01-15", timestamp="2026-01-15T00:00:00", level="deep"),
            SleepLevel(date="2026-01-15", timestamp="2026-01-15T06:00:00", level="awake"),
        ])
        w = _make_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T01:00:00", value=0),
            HeartRateReading(timestamp="2026-01-15T02:00:00", value=50),
        ])
        result = compute_sleeping_hr_trend([w], [sleep])
        assert len(result) == 1
        assert result[0].avg_sleeping_bpm == 50.0
        assert result[0].sample_count == 1


# ---------------------------------------------------------------------------
# Resting HR trend
# ---------------------------------------------------------------------------

class TestRestingHRTrend:
    def test_first_day_ma_equals_self(self):
        metrics = [_make_metric("2026-01-15", 50)]
        result = compute_resting_hr_trend(metrics)
        assert len(result) == 1
        assert result[0].resting_bpm == 50
        assert result[0].ma7_bpm == 50.0

    def test_7_day_window_correct(self):
        metrics = [_make_metric(f"2026-01-{d:02d}", 40 + d) for d in range(10, 18)]
        result = compute_resting_hr_trend(metrics)
        # Day 7 (index 7, date 2026-01-17): window is days 10-17
        # Values: 50, 51, 52, 53, 54, 55, 56, 57 -> but only 7 in the window
        # Index 7: window from max(0,7-6)=1 to 7 inclusive: indices 1..7
        # Values: 51, 52, 53, 54, 55, 56, 57 -> avg = 54.0
        assert result[7].ma7_bpm == 54.0

    def test_none_resting_skipped_in_ma(self):
        metrics = [
            _make_metric("2026-01-10", 50),
            _make_metric("2026-01-11", None),
            _make_metric("2026-01-12", 60),
        ]
        result = compute_resting_hr_trend(metrics)
        # Day 2 (2026-01-12): window includes indices 0, 1, 2
        # Non-null values: 50, 60 -> avg = 55.0
        assert result[2].resting_bpm == 60
        assert result[2].ma7_bpm == 55.0
        assert result[1].resting_bpm is None


# ---------------------------------------------------------------------------
# HR Distribution
# ---------------------------------------------------------------------------

class TestHRDistribution:
    def test_5_bpm_bins(self):
        readings = [(62, None), (63, None), (67, None), (70, None)]
        result = compute_hr_distribution(readings)
        assert len(result) == 3
        assert result[0].bin_start == 60
        assert result[0].bin_end == 65
        assert result[0].count == 2
        assert result[1].bin_start == 65
        assert result[1].bin_end == 70
        assert result[1].count == 1
        assert result[2].bin_start == 70
        assert result[2].bin_end == 75
        assert result[2].count == 1

    def test_empty_readings(self):
        assert compute_hr_distribution([]) == []

    def test_zeros_excluded(self):
        readings = [(0, None), (60, None)]
        result = compute_hr_distribution(readings)
        assert len(result) == 1
        assert result[0].count == 1

    def test_boundary_value_in_correct_bin(self):
        """Value exactly at bin boundary goes to that bin."""
        readings = [(65, None)]
        result = compute_hr_distribution(readings)
        assert result[0].bin_start == 65
        assert result[0].bin_end == 70


# ---------------------------------------------------------------------------
# Weekly boxplots
# ---------------------------------------------------------------------------

class TestWeeklyBoxplots:
    def test_iso_week_grouping(self):
        # 2026-01-05 is a Monday (ISO week 2)
        # 2026-01-12 is a Monday (ISO week 3)
        metrics = [
            _make_metric("2026-01-05", 50),
            _make_metric("2026-01-06", 60),
            _make_metric("2026-01-12", 55),
        ]
        result = compute_weekly_resting_hr_boxplots(metrics)
        assert len(result) == 2
        assert result[0].iso_week == "2026-W02"
        assert result[0].day_count == 2
        assert result[1].iso_week == "2026-W03"
        assert result[1].day_count == 1

    def test_single_day_week(self):
        metrics = [_make_metric("2026-01-05", 50)]
        result = compute_weekly_resting_hr_boxplots(metrics)
        assert len(result) == 1
        box = result[0]
        assert box.min_bpm == 50.0
        assert box.q1_bpm == 50.0
        assert box.median_bpm == 50.0
        assert box.q3_bpm == 50.0
        assert box.max_bpm == 50.0

    def test_none_resting_excluded(self):
        metrics = [
            _make_metric("2026-01-05", None),
            _make_metric("2026-01-06", 60),
        ]
        result = compute_weekly_resting_hr_boxplots(metrics)
        assert len(result) == 1
        assert result[0].day_count == 1
        assert result[0].median_bpm == 60.0

    def test_five_number_summary(self):
        # 2026-01-05..09 Mon-Fri, same ISO week
        metrics = [
            _make_metric("2026-01-05", 40),
            _make_metric("2026-01-06", 45),
            _make_metric("2026-01-07", 50),
            _make_metric("2026-01-08", 55),
            _make_metric("2026-01-09", 60),
        ]
        result = compute_weekly_resting_hr_boxplots(metrics)
        assert len(result) == 1
        box = result[0]
        assert box.min_bpm == 40.0
        assert box.max_bpm == 60.0
        assert box.median_bpm == 50.0
