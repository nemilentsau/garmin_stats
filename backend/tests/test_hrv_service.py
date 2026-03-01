"""Tests for HRV service domain transformations."""

import pytest

import app.database as db
from app.models import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayHrv,
    HrvValue,
)
from app.services.hrv import load_hrv_insights


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
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
    with db._connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
            (metric.date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


def _insert_hrv_day(date: str, values: list[HrvValue]) -> None:
    payload = DayHrv(date=date, hrv_values=values, hrv_summaries=[])
    with db._connect() as con:
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
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:00:00+00:00", value=45.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:05:00+00:00", value=44.0),
            HrvValue(date="2026-01-15", timestamp="2026-01-15T00:10:00+00:00", value=46.0),
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
                timestamp=f"2026-01-15T00:{minute:02d}:00+00:00",
                value=60.0 + minute * 0.1,
            )
            for minute in range(25)
        ])

        insights = load_hrv_insights("2026-01-15")
        assert any(item.title == "HRV recovery signals look stable" for item in insights.insights)
        assert all(item.title != "Low HRV sample coverage" for item in insights.insights)
        assert sum(bucket.count for bucket in insights.status_mix) == 2

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
