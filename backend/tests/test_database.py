"""Tests for database.py — connection, storage, read-back."""

import os

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
    DaySkinTemp,
    DaySleep,
    DayWellness,
    PeriodHeartRateStats,
    PeriodHrvStats,
    PeriodMetricStats,
    PeriodSkinTempStats,
    PeriodSpo2Stats,
    PeriodSummary,
)


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
    def test_creates_all_required_tables(self, tmp_db):
        with db._connect() as con:
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "wellness_data" in tables
        assert "daily_metrics" in tables
        assert "ingest_meta" in tables

    def test_enables_wal_journal_mode(self, tmp_db):
        with db._connect() as con:
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


# ---------------------------------------------------------------------------
# count_rows
# ---------------------------------------------------------------------------

class TestCountRows:
    def test_returns_zero_for_empty_table(self):
        assert db._count_rows("daily_metrics") == 0

    def test_rejects_invalid_table_name(self):
        with pytest.raises(ValueError, match="Invalid table name"):
            db._count_rows("users; DROP TABLE daily_metrics")


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

class TestFingerprint:
    def test_detects_file_content_change(self, tmp_path):
        data_dir = tmp_path / "data"
        day_dir = data_dir / "2026-01-15"
        day_dir.mkdir(parents=True)
        fit_file = day_dir / "001_WELLNESS.fit"
        fit_file.write_bytes(b"AAAA")
        fp1 = db.compute_data_fingerprint(data_dir)

        fit_file.write_bytes(b"BBBB")
        stat = fit_file.stat()
        os.utime(fit_file, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 1))
        fp2 = db.compute_data_fingerprint(data_dir)

        assert fp1 != fp2

    def test_returns_stable_hash_for_nonexistent_dir(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        fp = db.compute_data_fingerprint(missing)
        assert isinstance(fp, str)
        assert len(fp) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Store and load round-trips
# ---------------------------------------------------------------------------

def _make_daily_metric(date: str, utc_offset_hours: float | None = None) -> DailyMetric:
    """Build a minimal DailyMetric for storage tests."""
    return DailyMetric(
        date=date,
        utc_offset_hours=utc_offset_hours,
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
    def test_wellness_survives_round_trip(self):
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

    def test_daily_metrics_survive_round_trip(self):
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

    def test_available_days_returned_sorted(self):
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

    def test_is_db_empty_true_when_no_metrics(self):
        assert db.is_db_empty() is True

    def test_is_db_empty_false_after_insert(self):
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
    def test_period_summary_survives_round_trip(self):
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

    def test_returns_none_when_no_summary_stored(self):
        assert db.load_period_summary() is None


# ---------------------------------------------------------------------------
# _delete_stale_day_rows
# ---------------------------------------------------------------------------

class TestDeleteStaleRows:
    def test_removes_dates_absent_from_parsed_input(self):
        date_keep = "2026-01-15"
        date_drop = "2026-01-16"
        now = "2026-01-15T00:00:00Z"

        tables = [
            (
                "wellness_data",
                DayWellness(date=date_keep).model_dump_json(),
                DayWellness(date=date_drop).model_dump_json(),
            ),
            (
                "sleep_data",
                DaySleep(date=date_keep).model_dump_json(),
                DaySleep(date=date_drop).model_dump_json(),
            ),
            (
                "hrv_data",
                DayHrv(date=date_keep).model_dump_json(),
                DayHrv(date=date_drop).model_dump_json(),
            ),
            (
                "skin_temp_data",
                DaySkinTemp(date=date_keep).model_dump_json(),
                DaySkinTemp(date=date_drop).model_dump_json(),
            ),
            (
                "daily_metrics",
                _make_daily_metric(date_keep).model_dump_json(),
                _make_daily_metric(date_drop).model_dump_json(),
            ),
        ]

        with db._connect() as con:
            for table, keep_payload, drop_payload in tables:
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    (date_keep, keep_payload, now),
                )
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    (date_drop, drop_payload, now),
                )
            con.commit()

            db._delete_stale_day_rows(con, [date_keep])
            con.commit()

            for table, _, _ in tables:
                rows = con.execute(f"SELECT date FROM {table} ORDER BY date").fetchall()
                assert [r["date"] for r in rows] == [date_keep]

    def test_empty_parsed_dates_deletes_all_rows(self):
        """When no dates are parsed, all per-day rows should be deleted."""
        now = "2026-01-15T00:00:00Z"
        tables = (
            "wellness_data", "sleep_data", "hrv_data",
            "skin_temp_data", "daily_metrics",
        )
        with db._connect() as con:
            for table in tables:
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    ("2026-01-15", "{}", now),
                )
            con.commit()

            db._delete_stale_day_rows(con, [])
            con.commit()

            for table in tables:
                count = con.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table}"
                ).fetchone()["cnt"]
                assert count == 0
