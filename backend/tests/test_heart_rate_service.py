"""Tests for heart-rate service domain transformations."""

import pytest

import app.infra.database as db
from app.domains.garmin_analytics.application.heart_rate import (
    load_heart_rate_insights as _load_heart_rate_insights,
)
from app.domains.garmin_analytics.infra.biometric_repository import (
    SqliteBiometricRepository,
)
from app.infra import cache
from app.models import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayWellness,
    HeartRateReading,
)


def load_heart_rate_insights(date: str | None = None):
    return _load_heart_rate_insights(SqliteBiometricRepository(), date)


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    cache.invalidate()
    db.init_db()
    yield


def _make_daily_metric(
    date: str,
    resting: int | None,
    sleep_score: int | None = 85,
    hrv_status: str | None = "balanced",
) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, median=72.0, resting=resting),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(nightly_avg=55.0, weekly_avg=52.0, status=hrv_status),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


def _insert_metric(
    date: str,
    resting: int | None,
    sleep_score: int | None = 85,
    hrv_status: str | None = "balanced",
) -> None:
    metric = _make_daily_metric(date, resting, sleep_score=sleep_score, hrv_status=hrv_status)
    with db._connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
            (date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


def _insert_wellness(date: str, readings: list[HeartRateReading]) -> None:
    payload = DayWellness(date=date, heart_rate=readings)
    with db._connect() as con:
        con.execute(
            "INSERT INTO wellness_data (date, data, updated_at) VALUES (?, ?, ?)",
            (date, payload.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


class TestHeartRateInsights:
    def test_defaults_to_latest_date_and_builds_recovery_and_quality(self):
        _insert_metric("2026-01-14", 46)
        _insert_metric("2026-01-15", 52, sleep_score=65, hrv_status="low")
        _insert_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T00:00:00+00:00", value=70),
            HeartRateReading(timestamp="2026-01-15T00:01:00+00:00", value=120),
            HeartRateReading(timestamp="2026-01-15T00:02:00+00:00", value=140),
        ])

        insights = load_heart_rate_insights()

        assert insights.date == "2026-01-15"
        assert insights.recovery.baseline_resting_7d == 46.0
        assert insights.recovery.delta_from_baseline == 6.0
        assert insights.recovery.status == "high"
        assert insights.quality.sample_count == 3
        assert insights.quality.coverage_start == "2026-01-15T00:00:00+00:00"
        assert insights.quality.coverage_end == "2026-01-15T00:02:00+00:00"
        assert insights.quality.coverage_hours == 0.03
        assert sum(zone.pct for zone in insights.zones) > 99
        titles = {item.title for item in insights.insights}
        assert "Resting HR is materially elevated" in titles
        assert "Sleep may be impacting recovery" in titles
        assert "HRV and resting HR are both unfavorable" in titles
        assert "Low sample coverage" in titles

    def test_unknown_date_raises_lookup_error(self):
        _insert_metric("2026-01-14", 46)

        with pytest.raises(LookupError, match="Day 2026-01-16 not found"):
            load_heart_rate_insights("2026-01-16")

    def test_handles_missing_intraday_data(self):
        _insert_metric("2026-01-14", 46)

        insights = load_heart_rate_insights("2026-01-14")
        assert insights.zones == []
        assert insights.quality.sample_count == 0
        assert any(item.title == "Low sample coverage" for item in insights.insights)

    def test_adds_positive_summary_when_recovery_signals_stable(self):
        _insert_metric("2026-01-14", 46, sleep_score=88, hrv_status="balanced")
        _insert_metric("2026-01-15", 46, sleep_score=90, hrv_status="balanced")
        _insert_wellness("2026-01-15", [
            HeartRateReading(timestamp="2026-01-15T00:00:00+00:00", value=60),
            HeartRateReading(timestamp="2026-01-15T00:01:00+00:00", value=62),
            HeartRateReading(timestamp="2026-01-15T00:02:00+00:00", value=64),
            HeartRateReading(timestamp="2026-01-15T00:03:00+00:00", value=66),
            HeartRateReading(timestamp="2026-01-15T00:04:00+00:00", value=68),
            HeartRateReading(timestamp="2026-01-15T00:05:00+00:00", value=70),
            HeartRateReading(timestamp="2026-01-15T00:06:00+00:00", value=72),
            HeartRateReading(timestamp="2026-01-15T00:07:00+00:00", value=74),
            HeartRateReading(timestamp="2026-01-15T00:08:00+00:00", value=76),
            HeartRateReading(timestamp="2026-01-15T00:09:00+00:00", value=78),
            HeartRateReading(timestamp="2026-01-15T00:10:00+00:00", value=80),
            HeartRateReading(timestamp="2026-01-15T00:11:00+00:00", value=82),
            HeartRateReading(timestamp="2026-01-15T00:12:00+00:00", value=84),
            HeartRateReading(timestamp="2026-01-15T00:13:00+00:00", value=86),
            HeartRateReading(timestamp="2026-01-15T00:14:00+00:00", value=88),
            HeartRateReading(timestamp="2026-01-15T00:15:00+00:00", value=90),
            HeartRateReading(timestamp="2026-01-15T00:16:00+00:00", value=92),
            HeartRateReading(timestamp="2026-01-15T00:17:00+00:00", value=94),
            HeartRateReading(timestamp="2026-01-15T00:18:00+00:00", value=96),
            HeartRateReading(timestamp="2026-01-15T00:19:00+00:00", value=98),
            HeartRateReading(timestamp="2026-01-15T00:20:00+00:00", value=100),
            HeartRateReading(timestamp="2026-01-15T00:21:00+00:00", value=102),
            HeartRateReading(timestamp="2026-01-15T00:22:00+00:00", value=104),
            HeartRateReading(timestamp="2026-01-15T00:23:00+00:00", value=106),
            HeartRateReading(timestamp="2026-01-15T00:24:00+00:00", value=108),
            HeartRateReading(timestamp="2026-01-15T00:25:00+00:00", value=110),
            HeartRateReading(timestamp="2026-01-15T00:26:00+00:00", value=112),
            HeartRateReading(timestamp="2026-01-15T00:27:00+00:00", value=114),
            HeartRateReading(timestamp="2026-01-15T00:28:00+00:00", value=116),
            HeartRateReading(timestamp="2026-01-15T00:29:00+00:00", value=118),
            HeartRateReading(timestamp="2026-01-15T00:30:00+00:00", value=120),
        ])

        insights = load_heart_rate_insights("2026-01-15")
        assert any(item.title == "Recovery signals look stable" for item in insights.insights)
        assert all(item.title != "Low sample coverage" for item in insights.insights)
