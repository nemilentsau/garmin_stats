"""Tests for HRV service domain transformations."""

import pytest

import app.bootstrap.schema as storage_schema
import app.infra.sqlite as sqlite
from app.domains.garmin_analytics.adapters import (
    SqliteBiometricRepository,
)
from app.domains.garmin_analytics.application.metric_insights import (
    get_hrv_insights as _get_hrv_insights,
)
from app.domains.garmin_analytics.domain.analysis import hrv_patterns
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
        assert insights.baseline is None  # only 2 metrics — below the 21-night floor
        titles = {item.title for item in insights.insights}
        assert "HRV appears suppressed" in titles
        assert "Acute recovery is below weekly trend" in titles
        assert "Sleep and HRV both indicate reduced recovery" in titles
        assert "Resting HR and HRV are diverging unfavorably" in titles
        assert "Low HRV sample coverage" in titles

    def test_windowed_baseline_and_rule_text(self):
        from datetime import date, timedelta

        start = date(2026, 1, 1)
        # Use varied priors (55–65 ms, median≈60, MAD≈3) so the window has genuine
        # spread and the degenerate-scale guard does not suppress z.
        for i in range(22):
            prior_avg = 55.0 + (i % 11)  # cycles 55,56,…,65 twice → spread ≈ 10 ms
            _insert_metric(_make_daily_metric(
                date=(start + timedelta(days=i)).isoformat(),
                nightly_avg=prior_avg, weekly_avg=prior_avg, hrv_status="balanced",
                sleep_score=85, resting_hr=46,
            ))
        _insert_metric(_make_daily_metric(
            date=(start + timedelta(days=22)).isoformat(),
            nightly_avg=20.0, weekly_avg=30.0, hrv_status="low",
            sleep_score=85, resting_hr=46,
        ))

        insights = load_hrv_insights()  # defaults baseline=60
        assert insights.baseline is not None
        assert insights.baseline.window_days == 60
        assert insights.baseline.selected_is_extreme is True
        z = insights.baseline.selected_z
        assert z is not None and z < -2
        # With median≈60, MAD-scale≈4.5, current=20: z ≈ -9. Confirm sane magnitude.
        assert z > -30  # not the ~1e10 garbage from the degenerate path

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

    def test_unbalanced_status_does_not_trigger_stable_signal(self):
        """stable_recovery_rule returns None for unbalanced HRV status (non-vacuous direct test)."""
        from app.domains.garmin_analytics.contracts import HrvDataQuality, HrvRecovery
        from app.domains.garmin_analytics.domain.insights.hrv_rules import (
            InsightContext,
            stable_recovery_rule,
        )

        ctx = InsightContext(
            selected=_make_daily_metric(
                date="2026-01-15",
                nightly_avg=61.0,
                weekly_avg=60.5,
                hrv_status="unbalanced",
                sleep_score=90,
                resting_hr=46,
            ),
            recovery=HrvRecovery(
                baseline_nightly_7d=60.0,
                delta_nightly_from_baseline=1.0,
                acute_gap_vs_weekly=0.5,
                status=None,
            ),
            quality=HrvDataQuality(sample_count=25),
            resting_delta=None,
        )
        # Direct rule call — guaranteed non-vacuous regardless of other rules.
        assert stable_recovery_rule(ctx) is None

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

    def test_selected_day_insights_omit_pattern_surfaces(self):
        _insert_metric(_make_daily_metric(
            date="2026-01-15",
            nightly_avg=60.0,
            weekly_avg=60.0,
            hrv_status="balanced",
            sleep_score=85,
            resting_hr=46,
        ))
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=60.0),
        ])

        result = load_hrv_insights("2026-01-15")

        assert not hasattr(result, "distribution")
        assert not hasattr(result, "day_of_week")

    def test_baseline_rule_fires_when_7d_below_baseline(self):
        from datetime import date, timedelta
        start = date(2026, 1, 1)
        for i in range(22):
            d = (start + timedelta(days=i)).isoformat()
            _insert_metric(_make_daily_metric(d, 70.0, 70.0, "balanced", 85, 46))
        for i in range(22, 30):
            d = (start + timedelta(days=i)).isoformat()
            _insert_metric(_make_daily_metric(d, 50.0, 50.0, "balanced", 85, 46))

        insights = load_hrv_insights()  # defaults baseline=60
        assert insights.baseline is not None
        assert insights.baseline.delta_7d_vs_baseline is not None
        assert insights.baseline.delta_7d_vs_baseline < -5
        titles = {item.title for item in insights.insights}
        assert "7-day baseline is trending below 60-day baseline" in titles

    def test_baseline_rule_silent_at_minus_5_boundary(self):
        from datetime import date, timedelta
        start = date(2026, 1, 1)
        for i in range(22):
            d = (start + timedelta(days=i)).isoformat()
            _insert_metric(_make_daily_metric(d, 70.0, 70.0, "balanced", 85, 46))
        for i in range(22, 30):
            d = (start + timedelta(days=i)).isoformat()
            _insert_metric(_make_daily_metric(d, 65.0, 65.0, "balanced", 85, 46))

        insights = load_hrv_insights()
        assert insights.baseline is not None
        assert insights.baseline.delta_7d_vs_baseline == -5.0
        titles = {item.title for item in insights.insights}
        assert "7-day baseline is trending below 60-day baseline" not in titles


class TestRecoveryStatusRule:
    def test_suppressed_status_with_negative_delta_keeps_delta_sentence(self):
        """A below-type status with a genuinely negative delta keeps the delta text."""
        from app.domains.garmin_analytics.contracts import HrvDataQuality, HrvRecovery
        from app.domains.garmin_analytics.domain.insights.hrv_rules import (
            InsightContext,
            recovery_status_rule,
        )

        ctx = InsightContext(
            selected=_make_daily_metric(
                date="2026-01-15",
                nightly_avg=45.0,
                weekly_avg=60.0,
                hrv_status="low",
                sleep_score=65,
                resting_hr=52,
            ),
            recovery=HrvRecovery(
                baseline_nightly_7d=60.0,
                delta_nightly_from_baseline=-15.0,
                acute_gap_vs_weekly=-15.0,
                status="suppressed",
            ),
            quality=HrvDataQuality(sample_count=10),
            resting_delta=None,
        )
        result = recovery_status_rule(ctx)
        assert result is not None
        assert "-15.0 ms versus the prior 7-day baseline" in result.detail


class TestStdev:
    def test_high_overnight_stdev_no_longer_emits_volatility_insight(self):
        """overnight_volatility_rule was removed: its >25ms threshold was unreachable
        and its premise inverted (FINDINGS OQ#11). High overnight stdev with suppressed
        recovery -- the exact condition that used to fire it -- must now emit nothing."""
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
        # Wide-ranging values produce stdev > 25, which used to trip the old rule.
        _insert_hrv_day("2026-01-15", [
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00", value=20.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:05:00", value=80.0),
        ])

        result = load_hrv_insights("2026-01-15")
        titles = {item.title for item in result.insights}
        assert "High overnight HRV volatility" not in titles


class TestStreak:
    # The streak count is an internal input to the low-streak insight rule (not serialized),
    # so coverage lives on the observable insight: it fires at >= 3 consecutive low days,
    # stays silent below the threshold, and ignores non-low statuses. These three cases
    # exercise the streak counting (accumulate + break) and the status gate through the
    # only consumer that exists.
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



class TestTrajectory:
    def test_falling_trajectory_no_longer_emits_insight(self):
        """falling_trajectory_rule was removed: overnight HRV rises ~+10ms on the median
        night and "falling" (4% of nights) is noise-indistinguishable (Q12). A falling
        trajectory with suppressed recovery -- the condition that used to fire it -- must
        emit nothing."""
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
        titles = {item.title for item in result.insights}
        assert "HRV declined through the night" not in titles


class TestDayOfWeek:
    def test_returns_7_buckets_sorted_mon_to_sun(self):
        metrics = [_make_daily_metric(
            date="2026-01-15", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        )]

        result = hrv_patterns.compute_day_of_week(metrics)

        assert len(result) == 7
        expected = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert [b.day for b in result] == expected
        assert [b.day_index for b in result] == list(range(7))

    def test_averages_grouped_by_weekday(self):
        metrics = [
            _make_daily_metric(
            date="2026-01-05", nightly_avg=40.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
            ),
            _make_daily_metric(
                date="2026-01-12", nightly_avg=60.0, weekly_avg=50.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ),
        ]

        result = hrv_patterns.compute_day_of_week(metrics)
        monday = result[0]
        assert monday.day == "Mon"
        assert monday.avg_nightly == 50.0
        assert monday.sample_count == 2

    def test_days_with_no_data_have_none_avg(self):
        metrics = [_make_daily_metric(
            date="2026-01-05", nightly_avg=50.0, weekly_avg=50.0,
            hrv_status="balanced", sleep_score=80, resting_hr=46,
        )]

        result = hrv_patterns.compute_day_of_week(metrics)
        tuesday = result[1]
        assert tuesday.avg_nightly is None
        assert tuesday.sample_count == 0

    def test_none_nightly_avg_excluded(self):
        metrics = [
            _make_daily_metric(
                date="2026-01-05", nightly_avg=None, weekly_avg=50.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ),
            _make_daily_metric(
                date="2026-01-12", nightly_avg=50.0, weekly_avg=50.0,
                hrv_status="balanced", sleep_score=80, resting_hr=46,
            ),
        ]

        result = hrv_patterns.compute_day_of_week(metrics)
        monday = result[0]
        assert monday.avg_nightly == 50.0
        assert monday.sample_count == 1
