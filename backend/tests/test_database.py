"""Tests for database.py — connection, storage, read-back."""

import os
import tempfile
import pytest
from pathlib import Path

from app.models import (
    DayWellness,
    DaySleep,
    DayHrv,
    DaySkinTemp,
    DailyMetric,
    DailyHeartRateStats,
    DailyMetricStats,
    DailyBodyBatteryStats,
    DailyHrvStats,
    DailySleepStats,
    DailySkinTempStats,
    PeriodSummary,
    PeriodHeartRateStats,
    PeriodMetricStats,
    PeriodHrvStats,
    PeriodSpo2Stats,
    PeriodSkinTempStats,
)
import app.database as db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Use a temporary DB for each test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield test_db


# ---------------------------------------------------------------------------
# init & schema
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_tables(self, tmp_db):
        with db._connect() as con:
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "wellness_data" in tables
        assert "daily_metrics" in tables
        assert "ingest_meta" in tables

    def test_wal_mode(self, tmp_db):
        with db._connect() as con:
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


# ---------------------------------------------------------------------------
# count_rows
# ---------------------------------------------------------------------------

class TestCountRows:
    def test_valid_table(self):
        assert db._count_rows("daily_metrics") == 0

    def test_invalid_table_raises(self):
        with pytest.raises(ValueError, match="Invalid table name"):
            db._count_rows("users; DROP TABLE daily_metrics")


# ---------------------------------------------------------------------------
# Store and load round-trips
# ---------------------------------------------------------------------------

def _make_daily_metric(date: str) -> DailyMetric:
    """Build a minimal DailyMetric for storage tests."""
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, resting=48),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(nightly_avg=55.0, weekly_avg=52.0, status="balanced"),
        sleep=DailySleepStats(score=85),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


class TestStoreAndLoad:
    def test_wellness_round_trip(self):
        wellness = DayWellness(date="2026-01-15")
        with db._connect() as con:
            con.execute(
                "INSERT INTO wellness_data (date, data, updated_at) VALUES (?, ?, ?)",
                ("2026-01-15", wellness.model_dump_json(), "2026-01-15T00:00:00Z"),
            )
            con.commit()
        loaded = db.load_wellness("2026-01-15")
        assert len(loaded) == 1
        assert loaded[0].date == "2026-01-15"

    def test_daily_metrics_round_trip(self):
        metric = _make_daily_metric("2026-01-15")
        with db._connect() as con:
            con.execute(
                "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                ("2026-01-15", metric.model_dump_json(), "2026-01-15T00:00:00Z"),
            )
            con.commit()
        loaded = db.load_daily_metrics()
        assert len(loaded) == 1
        assert loaded[0].heart_rate.avg == 70.0
        assert loaded[0].heart_rate.resting == 48

    def test_available_days(self):
        for date in ["2026-01-15", "2026-01-16", "2026-01-17"]:
            metric = _make_daily_metric(date)
            with db._connect() as con:
                con.execute(
                    "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                    (date, metric.model_dump_json(), "now"),
                )
                con.commit()
        days = db.load_available_days()
        assert days == ["2026-01-15", "2026-01-16", "2026-01-17"]

    def test_is_db_empty_true(self):
        assert db.is_db_empty() is True

    def test_is_db_empty_false(self):
        metric = _make_daily_metric("2026-01-15")
        with db._connect() as con:
            con.execute(
                "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                ("2026-01-15", metric.model_dump_json(), "now"),
            )
            con.commit()
        assert db.is_db_empty() is False


# ---------------------------------------------------------------------------
# Period summary storage
# ---------------------------------------------------------------------------

class TestPeriodSummary:
    def test_store_and_load(self):
        period = PeriodSummary(
            heart_rate=PeriodHeartRateStats(avg=70.0, avg_resting=48.0),
            stress=PeriodMetricStats(avg=25.0),
            respiration=PeriodMetricStats(avg=14.0),
            hrv=PeriodHrvStats(avg_nightly=55.0, total_days=30),
            spo2=PeriodSpo2Stats(avg=96.0, total_days=30),
            skin_temp=PeriodSkinTempStats(avg_deviation=0.1, days_tracked=28),
        )
        with db._connect() as con:
            con.execute(
                "INSERT INTO ingest_meta (key, value) VALUES (?, ?)",
                ("period_summary", period.model_dump_json()),
            )
            con.commit()
        loaded = db.load_period_summary()
        assert loaded is not None
        assert loaded.heart_rate.avg == 70.0
        assert loaded.hrv.total_days == 30

    def test_load_returns_none_when_missing(self):
        assert db.load_period_summary() is None
