"""Tests for Garmin sync SQLite ingest adapter behavior."""

import app.domains.garmin_sync.infra.sqlite_ingest as ingest_db
import app.infra.sqlite as sqlite
from app.domains.garmin_health.contracts import (
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
)
from app.domains.garmin_sync.infra.filesystem import compute_data_fingerprint


def _make_daily_metric(date: str, utc_offset_hours: float | None = None) -> DailyMetric:
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


def _write_fit_day(data_dir, date: str, filename: str = "001_WELLNESS.fit"):
    fit_file = data_dir / date / filename
    fit_file.parent.mkdir(parents=True, exist_ok=True)
    fit_file.write_bytes(f"{date}:{filename}".encode())


def _store_current_fingerprint(data_dir):
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO ingest_meta (key, value) VALUES (?, ?)",
            ("data_fingerprint", compute_data_fingerprint(data_dir)),
        )
        con.commit()


def _insert_raw_day(date: str, updated_at: str):
    rows = (
        ("wellness_data", DayWellness(date=date).model_dump_json()),
        ("sleep_data", DaySleep(date=date).model_dump_json()),
        ("hrv_data", DayHrv(date=date).model_dump_json()),
        ("skin_temp_data", DaySkinTemp(date=date).model_dump_json()),
    )
    with sqlite.connect() as con:
        for table, payload in rows:
            con.execute(
                f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                (date, payload, updated_at),
            )
        con.commit()


def _insert_daily_metric(date: str, updated_at: str):
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
            (date, _make_daily_metric(date).model_dump_json(), updated_at),
        )
        con.commit()


class TestIngestStatus:
    def test_needs_ingest_when_fingerprint_is_missing(self, tmp_path):
        data_dir = tmp_path / "data"
        _write_fit_day(data_dir, "2026-01-15")

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is True
        assert status.days_in_db == 0
        assert status.days_on_disk == 1

    def test_in_sync_when_fingerprint_dates_and_timestamps_match(self, tmp_path):
        data_dir = tmp_path / "data"
        date = "2026-01-15"
        updated_at = "2026-01-15T00:00:00+00:00"
        _write_fit_day(data_dir, date)
        _insert_raw_day(date, updated_at)
        _insert_daily_metric(date, updated_at)
        _store_current_fingerprint(data_dir)

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is False
        assert status.days_in_db == 1
        assert status.days_on_disk == 1

    def test_in_sync_status_is_idempotent_for_unchanged_inputs(self, tmp_path):
        data_dir = tmp_path / "data"
        date = "2026-01-15"
        updated_at = "2026-01-15T00:00:00+00:00"
        _write_fit_day(data_dir, date)
        _insert_raw_day(date, updated_at)
        _insert_daily_metric(date, updated_at)
        _store_current_fingerprint(data_dir)

        first = ingest_db.check_ingest_status(data_dir)
        second = ingest_db.check_ingest_status(data_dir)

        assert first == second
        assert second.needs_ingest is False

    def test_needs_ingest_when_source_fingerprint_changed(self, tmp_path):
        data_dir = tmp_path / "data"
        date = "2026-01-15"
        updated_at = "2026-01-15T00:00:00+00:00"
        _write_fit_day(data_dir, date)
        _insert_raw_day(date, updated_at)
        _insert_daily_metric(date, updated_at)
        with sqlite.connect() as con:
            con.execute(
                "INSERT INTO ingest_meta (key, value) VALUES (?, ?)",
                ("data_fingerprint", "old-fingerprint"),
            )
            con.commit()

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is True
        assert status.days_in_db == 1
        assert status.days_on_disk == 1

    def test_needs_ingest_when_daily_metrics_are_missing_disk_days(self, tmp_path):
        data_dir = tmp_path / "data"
        _write_fit_day(data_dir, "2026-01-15")
        _write_fit_day(data_dir, "2026-01-16")
        updated_at = "2026-01-15T00:00:00+00:00"
        _insert_raw_day("2026-01-15", updated_at)
        _insert_raw_day("2026-01-16", updated_at)
        _insert_daily_metric("2026-01-15", updated_at)
        _store_current_fingerprint(data_dir)

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is True
        assert status.days_in_db == 1
        assert status.days_on_disk == 2

    def test_needs_ingest_when_daily_metrics_include_dates_not_on_disk(self, tmp_path):
        data_dir = tmp_path / "data"
        updated_at = "2026-01-15T00:00:00+00:00"
        _write_fit_day(data_dir, "2026-01-15")
        _insert_raw_day("2026-01-15", updated_at)
        _insert_daily_metric("2026-01-15", updated_at)
        _insert_daily_metric("2026-01-16", updated_at)
        _store_current_fingerprint(data_dir)

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is True
        assert status.days_in_db == 2
        assert status.days_on_disk == 1

    def test_needs_ingest_when_raw_day_tables_are_incomplete(self, tmp_path):
        data_dir = tmp_path / "data"
        date = "2026-01-15"
        updated_at = "2026-01-15T00:00:00+00:00"
        _write_fit_day(data_dir, date)
        _insert_daily_metric(date, updated_at)
        with sqlite.connect() as con:
            con.execute(
                "INSERT INTO wellness_data (date, data, updated_at) VALUES (?, ?, ?)",
                (date, DayWellness(date=date).model_dump_json(), updated_at),
            )
            con.commit()
        _store_current_fingerprint(data_dir)

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is True
        assert status.days_in_db == 1
        assert status.days_on_disk == 1

    def test_needs_ingest_when_daily_metrics_are_older_than_raw_tables(self, tmp_path):
        data_dir = tmp_path / "data"
        date = "2026-01-15"
        _write_fit_day(data_dir, date)
        _insert_raw_day(date, "2026-04-08T15:18:35+00:00")
        _insert_daily_metric(date, "2026-03-01T00:00:00+00:00")
        _store_current_fingerprint(data_dir)

        status = ingest_db.check_ingest_status(data_dir)

        assert status.needs_ingest is True
        assert status.days_in_db == 1
        assert status.days_on_disk == 1


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

        with sqlite.connect() as con:
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

            ingest_db._delete_stale_day_rows(con, [date_keep])
            con.commit()

            for table, _, _ in tables:
                rows = con.execute(f"SELECT date FROM {table} ORDER BY date").fetchall()
                assert [row["date"] for row in rows] == [date_keep]

    def test_empty_parsed_dates_deletes_all_rows(self):
        now = "2026-01-15T00:00:00Z"
        tables = (
            "wellness_data",
            "sleep_data",
            "hrv_data",
            "skin_temp_data",
            "daily_metrics",
        )
        with sqlite.connect() as con:
            for table in tables:
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    ("2026-01-15", "{}", now),
                )
            con.commit()

            ingest_db._delete_stale_day_rows(con, [])
            con.commit()

            for table in tables:
                count = con.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table}"
                ).fetchone()["cnt"]
                assert count == 0
