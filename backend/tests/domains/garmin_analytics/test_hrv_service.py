"""Tests for HRV service domain transformations."""

import importlib
import inspect

import pytest

import app.bootstrap.schema as storage_schema
import app.infra.sqlite as sqlite
from app.domains.garmin_analytics.adapters import (
    SqliteBiometricRepository,
)
from app.domains.garmin_analytics.application.metric_insights import (
    get_hrv_insights as _get_hrv_insights,
)
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayHrv,
    HrvSummary,
    HrvValue,
)
from app.infra import cache


def load_hrv_insights(date: str | None = None):
    return _get_hrv_insights(SqliteBiometricRepository(), date)


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(sqlite, "DB_PATH", test_db)
    cache.invalidate()
    storage_schema.init_storage()
    yield


def _make_daily_metric(
    date: str,
    nightly_avg: float | None,
    weekly_avg: float | None,
    hrv_status: str | None,
    sleep_score: int | None,
    resting_hr: int | None,
) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, median=72.0, resting=resting_hr),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(nightly_avg=nightly_avg, weekly_avg=weekly_avg, status=hrv_status),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


def _insert_metric(metric: DailyMetric) -> None:
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
            (metric.date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


def _insert_hrv_day(
    date: str,
    values: list[HrvValue],
    summaries: list[HrvSummary] | None = None,
) -> None:
    payload = DayHrv(date=date, hrv_values=values, hrv_summaries=summaries or [])
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO hrv_data (date, data, updated_at) VALUES (?, ?, ?)",
            (date, payload.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


class TestHrvModuleBoundaries:
    def test_pattern_helpers_and_rules_have_dedicated_owners(self):
        patterns = importlib.import_module(
            "app.domains.garmin_analytics.domain.analysis.hrv_patterns",
        )
        analysis = importlib.import_module(
            "app.domains.garmin_analytics.domain.analysis.hrv",
        )
        insights = importlib.import_module(
            "app.domains.garmin_analytics.domain.insights.hrv",
        )
        rules = importlib.import_module(
            "app.domains.garmin_analytics.domain.insights.hrv_rules",
        )

        shared_helpers = {
            "compute_day_of_week",
            "compute_hrv_distribution",
            "compute_trajectory",
            "extract_baseline_bands",
        }
        for helper in shared_helpers:
            assert hasattr(patterns, helper)
            assert not hasattr(analysis, helper)

        insight_source = inspect.getsource(insights)
        assert "domain.analysis.hrv import" not in insight_source
        assert "domain.analysis.hrv_patterns" in insight_source
        assert hasattr(rules, "build_hrv_insights")
        assert not hasattr(insights, "_build_insights")


class TestHrvInsights:
    def test_builds_suppressed_recovery_and_cross_metric_insights(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0,
            weekly_avg=62.0,
            hrv_status="balanced",
            sleep_score=85,
            resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=45.0,
            weekly_avg=55.0,
            hrv_status="low",
            sleep_score=65,
            resting_hr=52,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=45.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:05:00", value=44.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:10:00", value=46.0),
        ])

        insights = load_hrv_insights()
        assert insights.date == "2026-01-15"
        assert insights.recovery.baseline_nightly_7d == 60.0
        assert insights.recovery.delta_nightly_from_baseline == -15.0
        assert insights.recovery.acute_gap_vs_weekly == -10.0
        assert insights.recovery.status == "suppressed"
        assert insights.quality.sample_count == 3
        assert insights.quality.coverage_hours == 0.17
        assert insights.trend_band.nightly_typical_low == 48.8
        assert insights.trend_band.nightly_typical_high == 56.2
        assert len(insights.intraday_segments) == 1
        segment = next(seg for seg in insights.intraday_segments if seg.key == "all")
        assert segment.sample_count == 3
        titles = {item.title for item in insights.insights}
        assert "HRV appears suppressed" in titles
        assert "Acute recovery is below weekly trend" in titles
        assert "Sleep and HRV both indicate reduced recovery" in titles
        assert "Resting HR and HRV are diverging unfavorably" in titles
        assert "Low HRV sample coverage" in titles

    def test_adds_stable_signal_when_metrics_look_good(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0,
            weekly_avg=60.0,
            hrv_status="balanced",
            sleep_score=88,
            resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=61.0,
            weekly_avg=60.5,
            hrv_status="balanced",
            sleep_score=90,
            resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(
                date="2026-01-15",
                timestamp=f"2026-01-15T00:{minute:02d}:00",
                value=60.0 + minute * 0.1,
            )
            for minute in range(25)
        ])

        insights = load_hrv_insights("2026-01-15")
        assert any(item.title == "HRV recovery signals look stable" for item in insights.insights)
        assert all(item.title != "Low HRV sample coverage" for item in insights.insights)
        assert sum(bucket.count for bucket in insights.status_mix) == 2

    def test_unbalanced_status_does_not_trigger_stable_signal_without_baseline(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=61.0,
            weekly_avg=60.5,
            hrv_status="unbalanced",
            sleep_score=90,
            resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(
                date="2026-01-15",
                timestamp=f"2026-01-15T00:{minute:02d}:00",
                value=60.0 + minute * 0.1,
            )
            for minute in range(25)
        ])

        insights = load_hrv_insights("2026-01-15")

        assert all(
            item.title != "HRV recovery signals look stable"
            for item in insights.insights
        )
        assert all(item.title != "Low HRV sample coverage" for item in insights.insights)

    def test_unknown_date_raises_lookup_error(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0,
            weekly_avg=60.0,
            hrv_status="balanced",
            sleep_score=85,
            resting_hr=46,
        ))

        with pytest.raises(LookupError, match="Day 2026-01-16 not found"):
            load_hrv_insights("2026-01-16")

    def test_builds_single_intraday_segment_with_all_readings(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=52.0,
            weekly_avg=53.0,
            hrv_status="balanced",
            sleep_score=82,
            resting_hr=48,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T01:00:00", value=51.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T01:05:00", value=53.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T13:00:00", value=46.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T13:05:00", value=47.0),
        ])

        insights = load_hrv_insights("2026-01-15")
        assert len(insights.intraday_segments) == 1
        segment = insights.intraday_segments[0]
        assert segment.key == "all"
        assert segment.sample_count == 4
        assert segment.avg == 49.2


class TestStdev:
    def test_stdev_computed_for_multiple_samples(self):
        """stdev of [45, 44, 46] with ddof=1 = 1.0"""
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0, weekly_avg=62.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=45.0, weekly_avg=55.0,
            hrv_status="low", sleep_score=65, resting_hr=52,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=45.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:05:00", value=44.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:10:00", value=46.0),
        ])

        result = load_hrv_insights("2026-01-15")
        assert result.intraday_segments[0].stdev == 1.0

    def test_stdev_none_for_single_sample(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=50.0),
        ])

        result = load_hrv_insights("2026-01-15")
        assert result.intraday_segments[0].stdev is None

    def test_high_stdev_with_suppressed_fires_volatility_insight(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0, weekly_avg=62.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=45.0, weekly_avg=55.0,
            hrv_status="low", sleep_score=80, resting_hr=46,
        ))
        # Wide-ranging values to produce stdev > 25
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=20.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:05:00", value=80.0),
        ])

        result = load_hrv_insights("2026-01-15")
        titles = {item.title for item in result.insights}
        assert "High overnight HRV volatility" in titles

    def test_high_stdev_with_stable_does_not_fire_volatility_insight(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0, weekly_avg=60.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=61.0, weekly_avg=60.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=20.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:05:00", value=80.0),
        ])

        result = load_hrv_insights("2026-01-15")
        titles = {item.title for item in result.insights}
        assert "High overnight HRV volatility" not in titles


class TestStreak:
    def test_three_consecutive_same_status_days(self):
        for d in ["2026-01-13", "2026-01-14", "2026-01-15"]:
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=40.0, weekly_avg=55.0,
                hrv_status="low", sleep_score=70, resting_hr=50,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=40.0),
            ])

        result = load_hrv_insights("2026-01-15")
        assert result.streak is not None
        assert result.streak.current_status == "Low"
        assert result.streak.streak_days == 3

    def test_single_day_streak_is_one(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14",
            nightly_avg=60.0, weekly_avg=60.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=40.0, weekly_avg=55.0,
            hrv_status="low", sleep_score=70, resting_hr=50,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=40.0),
        ])

        result = load_hrv_insights("2026-01-15")
        assert result.streak is not None
        assert result.streak.streak_days == 1

    def test_worst_recent_streak_finds_longest_bad_run(self):
        # Balanced, then 4 low, then 1 balanced, then 2 low (selected)
        dates = [f"2026-01-{d:02d}" for d in range(8, 16)]
        statuses = ["balanced", "low", "low", "low", "low", "balanced", "low", "low"]
        for d, s in zip(dates, statuses, strict=True):
            _insert_metric(_make_daily_metric(
                date=d,
                nightly_avg=40.0 if s == "low" else 60.0,
                weekly_avg=55.0,
                hrv_status=s, sleep_score=70, resting_hr=50,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=40.0),
            ])

        result = load_hrv_insights("2026-01-15")
        assert result.streak is not None
        assert result.streak.worst_recent_streak == 4

    def test_low_streak_ge_3_fires_warning_insight(self):
        for d in ["2026-01-13", "2026-01-14", "2026-01-15"]:
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=40.0, weekly_avg=55.0,
                hrv_status="low", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=40.0),
            ])

        result = load_hrv_insights("2026-01-15")
        titles = {item.title for item in result.insights}
        assert "Extended low HRV streak" in titles

    def test_low_streak_2_does_not_fire_insight(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-13",
            nightly_avg=60.0, weekly_avg=60.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        for d in ["2026-01-14", "2026-01-15"]:
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=40.0, weekly_avg=55.0,
                hrv_status="low", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=40.0),
            ])
        _insert_hrv_day("2026-01-13", [
            HrvValue(date="2026-01-13", timestamp="2026-01-13T00:00:00", value=60.0),
        ])

        result = load_hrv_insights("2026-01-15")
        titles = {item.title for item in result.insights}
        assert "Extended low HRV streak" not in titles

    def test_balanced_streak_ge_3_does_not_fire_insight(self):
        for d in ["2026-01-13", "2026-01-14", "2026-01-15"]:
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=60.0, weekly_avg=60.0,
                hrv_status="balanced", sleep_score=85, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=60.0),
            ])

        result = load_hrv_insights("2026-01-15")
        titles = {item.title for item in result.insights}
        assert "Extended low HRV streak" not in titles


class TestLongBaseline:
    def _insert_history(self, count: int, selected_date: str = "2026-02-15") -> None:
        """Insert `count` days before selected_date, plus the selected day itself."""
        for i in range(count, 0, -1):
            day_num = 15 - i
            month = 2 if day_num > 0 else 1
            d = f"2026-{month:02d}-{abs(day_num) if day_num <= 0 else day_num:02d}"
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=50.0 + i * 0.1, weekly_avg=52.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=50.0),
            ])
        _insert_metric(_make_daily_metric(
            date=selected_date, nightly_avg=48.0, weekly_avg=49.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day(selected_date, [
            HrvValue(date=selected_date, timestamp=f"{selected_date}T00:00:00", value=48.0),
        ])

    def test_returns_none_when_fewer_than_14_data_points(self):
        self._insert_history(13)
        result = load_hrv_insights("2026-02-15")
        assert result.long_baseline is None

    def test_computes_baseline_with_exactly_14_data_points(self):
        self._insert_history(14)
        result = load_hrv_insights("2026-02-15")
        assert result.long_baseline is not None
        assert result.long_baseline.baseline_30d is not None

    def test_delta_7d_vs_30d_computed_correctly(self):
        self._insert_history(20)
        result = load_hrv_insights("2026-02-15")
        assert result.long_baseline is not None
        baseline_7d = result.recovery.baseline_nightly_7d
        assert baseline_7d is not None
        assert result.long_baseline.baseline_30d is not None
        expected_delta = round(baseline_7d - result.long_baseline.baseline_30d, 1)
        assert result.long_baseline.delta_7d_vs_30d == expected_delta

    def test_delta_below_minus_5_fires_caution_insight(self):
        # Create 20 days of high nightly_avg, then drop for recent 7 days
        for i in range(20, 7, -1):
            day_num = 15 - i
            month = 2 if day_num > 0 else 1
            d = f"2026-{month:02d}-{abs(day_num) if day_num <= 0 else day_num:02d}"
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=65.0, weekly_avg=65.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=65.0),
            ])
        for i in range(7, 0, -1):
            day_num = 15 - i
            d = f"2026-02-{day_num:02d}"
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=55.0, weekly_avg=56.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=55.0),
            ])
        _insert_metric(_make_daily_metric(
            date="2026-02-15", nightly_avg=55.0, weekly_avg=56.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-02-15", [
            HrvValue(date="2026-02-15", timestamp="2026-02-15T00:00:00", value=55.0),
        ])

        result = load_hrv_insights("2026-02-15")
        assert result.long_baseline is not None
        assert result.long_baseline.delta_7d_vs_30d is not None
        assert result.long_baseline.delta_7d_vs_30d < -5
        titles = {item.title for item in result.insights}
        assert "7-day baseline is trending below 30-day average" in titles

    def test_delta_exactly_minus_5_does_not_fire_insight(self):
        # baseline_7d and baseline_30d differ by exactly 5
        # We need baseline_7d = baseline_30d - 5.0
        # 30d window (14+ days): all nightly_avg = 60.0 → baseline_30d = 60.0
        # 7d window: all nightly_avg = 55.0 → baseline_7d = 55.0
        # delta = 55.0 - 60.0 = -5.0 (exactly at boundary, should NOT fire)
        for i in range(20, 7, -1):
            day_num = 15 - i
            month = 2 if day_num > 0 else 1
            d = f"2026-{month:02d}-{abs(day_num) if day_num <= 0 else day_num:02d}"
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=60.0, weekly_avg=60.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=60.0),
            ])
        for i in range(7, 0, -1):
            day_num = 15 - i
            d = f"2026-02-{day_num:02d}"
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=55.0, weekly_avg=55.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=55.0),
            ])
        _insert_metric(_make_daily_metric(
            date="2026-02-15", nightly_avg=55.0, weekly_avg=55.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-02-15", [
            HrvValue(date="2026-02-15", timestamp="2026-02-15T00:00:00", value=55.0),
        ])

        result = load_hrv_insights("2026-02-15")
        assert result.long_baseline is not None
        titles = {item.title for item in result.insights}
        assert "7-day baseline is trending below 30-day average" not in titles

    def test_none_nightly_avg_days_excluded(self):
        # 13 valid + 5 None = 18 total, but only 13 non-null → should return None
        for i in range(18, 0, -1):
            day_num = 15 - i
            month = 2 if day_num > 0 else 1
            d = f"2026-{month:02d}-{abs(day_num) if day_num <= 0 else day_num:02d}"
            nightly = None if i > 13 else 50.0
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=nightly, weekly_avg=52.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=50.0),
            ])
        _insert_metric(_make_daily_metric(
            date="2026-02-15", nightly_avg=48.0, weekly_avg=49.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-02-15", [
            HrvValue(date="2026-02-15", timestamp="2026-02-15T00:00:00", value=48.0),
        ])

        result = load_hrv_insights("2026-02-15")
        assert result.long_baseline is None


class TestBaselineBands:
    def test_bands_extracted_when_summary_has_baseline_values(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day(
            "2026-01-15",
            [HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=50.0)],
            summaries=[HrvSummary(
                date="2026-01-15",
                status="balanced",
                baseline_low_upper=35.0,
                baseline_balanced_lower=40.0,
                baseline_balanced_upper=65.0,
                last_night_5_min_high=72.0,
            )],
        )

        result = load_hrv_insights("2026-01-15")
        assert result.baseline_bands is not None
        assert result.baseline_bands.baseline_low_upper == 35.0
        assert result.baseline_bands.baseline_balanced_lower == 40.0
        assert result.baseline_bands.baseline_balanced_upper == 65.0
        assert result.baseline_bands.five_min_high == 72.0

    def test_bands_none_when_no_summaries(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=50.0),
        ])

        result = load_hrv_insights("2026-01-15")
        assert result.baseline_bands is None

    def test_bands_none_when_summary_fields_all_null(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day(
            "2026-01-15",
            [HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=50.0)],
            summaries=[HrvSummary(
                date="2026-01-15",
                status="balanced",
                baseline_low_upper=None,
                baseline_balanced_lower=None,
                baseline_balanced_upper=None,
                last_night_5_min_high=None,
            )],
        )

        result = load_hrv_insights("2026-01-15")
        assert result.baseline_bands is None


class TestHrvDistribution:
    def _insert_days(self, nightly_values: list[float | None]) -> None:
        """Insert len(nightly_values) days, last day is selected."""
        for i, nightly in enumerate(nightly_values):
            d = f"2026-01-{i + 1:02d}"
            _insert_metric(_make_daily_metric(
                date=d, nightly_avg=nightly, weekly_avg=50.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ))
            _insert_hrv_day(d, [
                HrvValue(date=d, timestamp=f"{d}T00:00:00", value=50.0),
            ])

    def test_returns_none_when_fewer_than_7_days(self):
        self._insert_days([40.0, 42.0, 44.0, 46.0, 48.0, 50.0])

        result = load_hrv_insights("2026-01-06")
        assert result.distribution is None

    def test_returns_distribution_with_exactly_7_days(self):
        self._insert_days([40.0, 42.0, 44.0, 46.0, 48.0, 50.0, 52.0])

        result = load_hrv_insights("2026-01-07")
        assert result.distribution is not None
        assert result.distribution.total_days == 7

    def test_5ms_bin_width_verified(self):
        self._insert_days([40.0, 42.0, 44.0, 46.0, 48.0, 50.0, 52.0])

        result = load_hrv_insights("2026-01-07")
        assert result.distribution is not None
        for b in result.distribution.bins:
            assert b.bin_end - b.bin_start == 5.0

    def test_selected_percentile_highest_value_is_100(self):
        # Last value (selected) is highest
        self._insert_days([40.0, 42.0, 44.0, 46.0, 48.0, 50.0, 60.0])

        result = load_hrv_insights("2026-01-07")
        assert result.distribution is not None
        assert result.distribution.selected_percentile == 100.0

    def test_none_nightly_avg_values_excluded(self):
        # 5 valid + 3 None = 8 total, only 5 non-null → below threshold
        self._insert_days([40.0, 42.0, None, 46.0, None, None, 48.0, 50.0])

        result = load_hrv_insights("2026-01-08")
        assert result.distribution is None

    def test_boundary_value_placed_in_correct_bin(self):
        # 45.0 should go in bin [45, 50), not [40, 45)
        self._insert_days([30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0])

        result = load_hrv_insights("2026-01-07")
        assert result.distribution is not None
        bin_45 = next(
            (b for b in result.distribution.bins if b.bin_start == 45.0), None,
        )
        assert bin_45 is not None
        assert bin_45.count == 1
        bin_40 = next(
            (b for b in result.distribution.bins if b.bin_start == 40.0), None,
        )
        assert bin_40 is not None
        assert bin_40.count == 1


class TestTrajectory:
    def test_returns_none_when_fewer_than_6_readings(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp=f"2026-01-15T0{i}:00:00", value=50.0)
            for i in range(5)
        ])

        result = load_hrv_insights("2026-01-15")
        assert result.trajectory is None

    def test_computes_three_segment_averages(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        # 9 values evenly spaced: 00:00 to 08:00 (1h apart)
        # early=00-02:39 (0,1,2), mid=02:40-05:19 (3,4,5), late=05:20-08:00 (6,7,8)
        values = [
            HrvValue(date="2026-01-15", timestamp=f"2026-01-15T0{i}:00:00", value=40.0 + i * 3.0)
            for i in range(9)
        ]
        _insert_hrv_day("2026-01-15", values)

        result = load_hrv_insights("2026-01-15")
        assert result.trajectory is not None
        assert result.trajectory.early_avg is not None
        assert result.trajectory.mid_avg is not None
        assert result.trajectory.late_avg is not None
        # Verify late > early since values are increasing
        assert result.trajectory.late_avg > result.trajectory.early_avg

    def test_rising_direction_when_late_exceeds_early_by_more_than_5(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        # early ~30, late ~50 → diff > 5 → rising
        values = [
            HrvValue(date="2026-01-15", timestamp=f"2026-01-15T0{i}:00:00", value=30.0 + i * 3.0)
            for i in range(9)
        ]
        _insert_hrv_day("2026-01-15", values)

        result = load_hrv_insights("2026-01-15")
        assert result.trajectory is not None
        assert result.trajectory.direction == "rising"

    def test_falling_direction_when_early_exceeds_late_by_more_than_5(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        # early ~60, late ~36 → diff < -5 → falling
        values = [
            HrvValue(date="2026-01-15", timestamp=f"2026-01-15T0{i}:00:00", value=60.0 - i * 3.0)
            for i in range(9)
        ]
        _insert_hrv_day("2026-01-15", values)

        result = load_hrv_insights("2026-01-15")
        assert result.trajectory is not None
        assert result.trajectory.direction == "falling"

    def test_flat_direction_when_difference_within_5(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        # All values ~50 → |diff| ≤ 5 → flat
        values = [
            HrvValue(date="2026-01-15", timestamp=f"2026-01-15T0{i}:00:00", value=50.0)
            for i in range(9)
        ]
        _insert_hrv_day("2026-01-15", values)

        result = load_hrv_insights("2026-01-15")
        assert result.trajectory is not None
        assert result.trajectory.direction == "flat"

    def test_falling_with_suppressed_fires_insight(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-14", nightly_avg=60.0, weekly_avg=60.0,
            hrv_status="balanced", sleep_score=85, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=45.0, weekly_avg=55.0,
            hrv_status="low", sleep_score=80, resting_hr=46,
        ))
        # Falling trajectory: early ~60, late ~36
        values = [
            HrvValue(date="2026-01-15", timestamp=f"2026-01-15T0{i}:00:00", value=60.0 - i * 3.0)
            for i in range(9)
        ]
        _insert_hrv_day("2026-01-15", values)

        result = load_hrv_insights("2026-01-15")
        assert result.trajectory is not None
        assert result.trajectory.direction == "falling"
        titles = {item.title for item in result.insights}
        assert "HRV declined through the night" in titles


class TestDayOfWeek:
    def test_returns_7_buckets_sorted_mon_to_sun(self):
        # Single day is enough to verify structure
        _insert_metric(_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=50.0),
        ])

        result = load_hrv_insights("2026-01-15")
        assert len(result.day_of_week) == 7
        expected = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert [b.day for b in result.day_of_week] == expected
        assert [b.day_index for b in result.day_of_week] == list(range(7))

    def test_averages_grouped_by_weekday(self):
        # 2026-01-05 = Monday, 2026-01-12 = Monday
        _insert_metric(_make_daily_metric(
            date="2026-01-05", nightly_avg=40.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-12", nightly_avg=60.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-05", [
            HrvValue(date="2026-01-05", timestamp="2026-01-05T00:00:00", value=40.0),
        ])
        _insert_hrv_day("2026-01-12", [
            HrvValue(date="2026-01-12", timestamp="2026-01-12T00:00:00", value=60.0),
        ])

        result = load_hrv_insights("2026-01-12")
        monday = result.day_of_week[0]
        assert monday.day == "Mon"
        assert monday.avg_nightly == 50.0
        assert monday.sample_count == 2

    def test_days_with_no_data_have_none_avg(self):
        # Only insert a Monday (2026-01-05)
        _insert_metric(_make_daily_metric(
            date="2026-01-05", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-05", [
            HrvValue(date="2026-01-05", timestamp="2026-01-05T00:00:00", value=50.0),
        ])

        result = load_hrv_insights("2026-01-05")
        tuesday = result.day_of_week[1]
        assert tuesday.avg_nightly is None
        assert tuesday.sample_count == 0

    def test_none_nightly_avg_excluded(self):
        # 2026-01-05 = Monday with None nightly_avg, 2026-01-12 = Monday with 50.0
        _insert_metric(_make_daily_metric(
            date="2026-01-05", nightly_avg=None, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_metric(_make_daily_metric(
            date="2026-01-12", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        ))
        _insert_hrv_day("2026-01-05", [
            HrvValue(date="2026-01-05", timestamp="2026-01-05T00:00:00", value=40.0),
        ])
        _insert_hrv_day("2026-01-12", [
            HrvValue(date="2026-01-12", timestamp="2026-01-12T00:00:00", value=50.0),
        ])

        result = load_hrv_insights("2026-01-12")
        monday = result.day_of_week[0]
        assert monday.avg_nightly == 50.0
        assert monday.sample_count == 1
