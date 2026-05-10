"""SQLite ingest adapter for Garmin sync workflows."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from app.domains.garmin_health.contracts import DayData
from app.domains.garmin_health.domain.daily import compute_daily_metrics
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
from app.domains.garmin_sync.filesystem import compute_data_fingerprint
from app.infra import cache
from app.infra.sqlite import connect
from app.parser import get_files_by_day, parse_all_days, parse_day

log = logging.getLogger(__name__)

_ingest_lock = threading.Lock()
_RAW_DAY_TABLES = (
    "wellness_data",
    "sleep_data",
    "hrv_data",
    "skin_temp_data",
)
_PER_DAY_TABLES = (*_RAW_DAY_TABLES, "daily_metrics")
_VALID_INGEST_TABLES = frozenset((*_PER_DAY_TABLES, "ingest_meta"))


def _get_meta(key: str) -> str | None:
    """Read a single ingest metadata value."""
    with connect() as con:
        row = con.execute(
            "SELECT value FROM ingest_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def _table_dates(con: sqlite3.Connection, table: str) -> set[str]:
    if table not in _VALID_INGEST_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    rows = con.execute(f"SELECT date FROM {table}").fetchall()
    return {row["date"] for row in rows}


def _has_stale_daily_metrics(con: sqlite3.Connection) -> bool:
    row = con.execute(
        """
        SELECT 1
        FROM daily_metrics dm
        JOIN (
            SELECT date, MAX(updated_at) AS updated_at
            FROM (
                SELECT date, updated_at FROM wellness_data
                UNION ALL SELECT date, updated_at FROM sleep_data
                UNION ALL SELECT date, updated_at FROM hrv_data
                UNION ALL SELECT date, updated_at FROM skin_temp_data
            )
            GROUP BY date
        ) raw ON raw.date = dm.date
        WHERE raw.updated_at > dm.updated_at
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def check_ingest_status(data_dir: Path) -> IngestStatus:
    """Compare stored fingerprint and derived table integrity."""
    stored = _get_meta("data_fingerprint")
    current = compute_data_fingerprint(data_dir)
    disk_dates = set(get_files_by_day(data_dir))
    with connect() as con:
        daily_dates = _table_dates(con, "daily_metrics")
        raw_dates_mismatch = any(
            _table_dates(con, table) != disk_dates
            for table in _RAW_DAY_TABLES
        )
        derived_out_of_sync = (
            daily_dates != disk_dates
            or raw_dates_mismatch
            or _has_stale_daily_metrics(con)
        )
    return IngestStatus(
        needs_ingest=stored != current or derived_out_of_sync,
        last_ingest_time=_get_meta("last_ingest_time"),
        days_in_db=len(daily_dates),
        days_on_disk=len(disk_dates),
    )


def ingest_all(data_dir: Path) -> IngestResult:
    """Parse all FIT files and store results in SQLite."""
    acquired = _ingest_lock.acquire(blocking=False)
    if not acquired:
        raise RuntimeError("Ingest already in progress")

    try:
        t0 = time.monotonic()
        all_days = parse_all_days(data_dir)

        now = datetime.now(UTC).isoformat()
        with connect() as con, con:
            _delete_stale_day_rows(con, [day.date for day in all_days])
            _upsert_parsed_day_data(con, all_days, now)

            meta_upsert = (
                "INSERT OR REPLACE INTO ingest_meta"
                " (key, value) VALUES (?, ?)"
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            meta = {
                "last_ingest_time": now,
                "duration_ms": str(duration_ms),
                "data_fingerprint": compute_data_fingerprint(data_dir),
                "days_ingested": str(len(all_days)),
            }
            for key, value in meta.items():
                con.execute(meta_upsert, (key, value))

        cache.invalidate()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info("Ingested %d days in %d ms", len(all_days), duration_ms)
        return IngestResult(days_ingested=len(all_days), duration_ms=duration_ms)
    finally:
        _ingest_lock.release()


def ingest_dates(data_dir: Path, dates: list[str]) -> IngestResult:
    """Parse and upsert only the specified dates."""
    if not dates:
        return IngestResult(days_ingested=0, duration_ms=0)

    acquired = _ingest_lock.acquire(blocking=False)
    if not acquired:
        raise RuntimeError("Ingest already in progress")

    try:
        t0 = time.monotonic()
        date_set = set(dates)
        files_by_day = get_files_by_day(data_dir)
        parsed_days = [
            parse_day(day, files)
            for day, files in sorted(files_by_day.items())
            if day in date_set
        ]

        now = datetime.now(UTC).isoformat()
        with connect() as con, con:
            _upsert_parsed_day_data(con, parsed_days, now)

            meta_upsert = (
                "INSERT OR REPLACE INTO ingest_meta"
                " (key, value) VALUES (?, ?)"
            )
            con.execute(
                meta_upsert,
                ("data_fingerprint", compute_data_fingerprint(data_dir)),
            )
            con.execute(meta_upsert, ("last_ingest_time", now))

        cache.invalidate()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "Ingested %d days (incremental) in %d ms",
            len(parsed_days),
            duration_ms,
        )
        return IngestResult(days_ingested=len(parsed_days), duration_ms=duration_ms)
    finally:
        _ingest_lock.release()


def _upsert_parsed_day_data(
    con: sqlite3.Connection,
    days: list[DayData],
    updated_at: str,
) -> None:
    """Persist parsed raw day slices and their derived canonical daily metrics."""
    upsert = "INSERT OR REPLACE INTO {} (date, data, updated_at) VALUES (?, ?, ?)"

    for day in days:
        con.execute(
            upsert.format("wellness_data"),
            (day.date, day.wellness.model_dump_json(), updated_at),
        )
        con.execute(
            upsert.format("sleep_data"),
            (day.date, day.sleep.model_dump_json(), updated_at),
        )
        con.execute(
            upsert.format("hrv_data"),
            (day.date, day.hrv.model_dump_json(), updated_at),
        )
        con.execute(
            upsert.format("skin_temp_data"),
            (day.date, day.skin_temp.model_dump_json(), updated_at),
        )

    for metric in compute_daily_metrics(days):
        con.execute(
            upsert.format("daily_metrics"),
            (metric.date, metric.model_dump_json(), updated_at),
        )


def _delete_stale_day_rows(con: sqlite3.Connection, parsed_dates: list[str]) -> None:
    """Delete DB rows for dates no longer present in parsed input."""
    if not parsed_dates:
        for table in _PER_DAY_TABLES:
            con.execute(f"DELETE FROM {table}")
        return

    placeholders = ", ".join("?" for _ in parsed_dates)
    for table in _PER_DAY_TABLES:
        con.execute(
            f"DELETE FROM {table} WHERE date NOT IN ({placeholders})",
            parsed_dates,
        )


class DatabaseIngestGateway:
    """Adapt SQLite ingest functions to the workflow ingest port."""

    def check_status(self, data_dir: Path) -> IngestStatus:
        return check_ingest_status(data_dir)

    def ingest_all(self, data_dir: Path) -> IngestResult:
        return ingest_all(data_dir)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        return ingest_dates(data_dir, dates)
