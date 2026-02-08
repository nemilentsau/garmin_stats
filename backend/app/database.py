"""
SQLite persistence layer for Garmin Stats.

Write path (ingest):  FIT files → parser → stats → SQLite
Read path (API):      SQLite → reconstruct Pydantic models → API response
"""

import hashlib
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    DayWellness,
    DaySleep,
    DayHrv,
    DaySkinTemp,
    DailyMetric,
    DailyAggregatesResponse,
    IngestResult,
    IngestStatus,
)
from .parser import get_files_by_day, parse_all_days
from .stats import compute_daily_aggregates

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "garmin_stats.db"

_ingest_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Schema & connection
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wellness_data  (date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sleep_data     (date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hrv_data       (date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS skin_temp_data (date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS daily_metrics  (date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ingest_meta    (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def init_db() -> None:
    """Create tables if they don't exist. Enable WAL mode."""
    con = get_connection()
    try:
        con.executescript(_SCHEMA)
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()
    finally:
        con.close()


def get_connection() -> sqlite3.Connection:
    """Return a connection with Row factory."""
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

def compute_data_fingerprint(data_dir: Path) -> str:
    """SHA-256 of sorted directory listing (dates + filenames)."""
    files_by_day = get_files_by_day(data_dir)
    parts: list[str] = []
    for date in sorted(files_by_day.keys()):
        day_files = files_by_day[date]
        filenames = sorted(
            f.name for type_files in day_files.values() for f in type_files
        )
        parts.append(f"{date}:{','.join(filenames)}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _get_meta(key: str) -> str | None:
    """Read a single metadata value."""
    con = get_connection()
    try:
        row = con.execute(
            "SELECT value FROM ingest_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None
    finally:
        con.close()


def _count_rows(table: str) -> int:
    """Count rows in a table."""
    con = get_connection()
    try:
        row = con.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()  # noqa: S608
        return row["cnt"]
    finally:
        con.close()


def check_ingest_status(data_dir: Path) -> IngestStatus:
    """Compare stored vs current fingerprint."""
    stored = _get_meta("data_fingerprint")
    current = compute_data_fingerprint(data_dir)
    days_in_db = _count_rows("daily_metrics")
    days_on_disk = len(get_files_by_day(data_dir))
    return IngestStatus(
        needs_ingest=stored != current,
        last_ingest_time=_get_meta("last_ingest_time"),
        days_in_db=days_in_db,
        days_on_disk=days_on_disk,
    )


# ---------------------------------------------------------------------------
# Ingest (write path)
# ---------------------------------------------------------------------------

def ingest_all(data_dir: Path) -> IngestResult:
    """Parse all FIT files and store results in SQLite.

    Uses a threading lock to prevent concurrent ingest calls.
    """
    acquired = _ingest_lock.acquire(blocking=False)
    if not acquired:
        raise RuntimeError("Ingest already in progress")

    try:
        t0 = time.monotonic()

        # Parse everything
        all_days = parse_all_days(data_dir)
        agg = compute_daily_aggregates(all_days)

        now = datetime.now(timezone.utc).isoformat()
        con = get_connection()
        try:
            with con:
                # Per-day data
                for day in all_days:
                    con.execute(
                        "INSERT OR REPLACE INTO wellness_data (date, data, updated_at) VALUES (?, ?, ?)",
                        (day.date, day.wellness.model_dump_json(), now),
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO sleep_data (date, data, updated_at) VALUES (?, ?, ?)",
                        (day.date, day.sleep.model_dump_json(), now),
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO hrv_data (date, data, updated_at) VALUES (?, ?, ?)",
                        (day.date, day.hrv.model_dump_json(), now),
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO skin_temp_data (date, data, updated_at) VALUES (?, ?, ?)",
                        (day.date, day.skin_temp.model_dump_json(), now),
                    )

                # Daily aggregates
                for metric in agg.daily:
                    con.execute(
                        "INSERT OR REPLACE INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                        (metric.date, metric.model_dump_json(), now),
                    )

                # Metadata
                fingerprint = compute_data_fingerprint(data_dir)
                duration_ms = int((time.monotonic() - t0) * 1000)
                meta = {
                    "last_ingest_time": now,
                    "duration_ms": str(duration_ms),
                    "data_fingerprint": fingerprint,
                    "days_ingested": str(len(all_days)),
                }
                for k, v in meta.items():
                    con.execute(
                        "INSERT OR REPLACE INTO ingest_meta (key, value) VALUES (?, ?)",
                        (k, v),
                    )
        finally:
            con.close()

        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info("Ingested %d days in %d ms", len(all_days), duration_ms)
        return IngestResult(days_ingested=len(all_days), duration_ms=duration_ms)
    finally:
        _ingest_lock.release()


def is_db_empty() -> bool:
    """Check if the DB has any ingested data."""
    return _count_rows("daily_metrics") == 0


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------

def load_daily_metrics() -> list[DailyMetric]:
    """Load all daily metrics from DB."""
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT data FROM daily_metrics ORDER BY date"
        ).fetchall()
        return [DailyMetric.model_validate_json(r["data"]) for r in rows]
    finally:
        con.close()


def load_wellness(date: str | None = None) -> list[DayWellness]:
    """Load wellness data, optionally filtered by date."""
    con = get_connection()
    try:
        if date:
            rows = con.execute(
                "SELECT data FROM wellness_data WHERE date = ?", (date,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT data FROM wellness_data ORDER BY date"
            ).fetchall()
        return [DayWellness.model_validate_json(r["data"]) for r in rows]
    finally:
        con.close()


def load_sleep(date: str | None = None) -> list[DaySleep]:
    """Load sleep data, optionally filtered by date."""
    con = get_connection()
    try:
        if date:
            rows = con.execute(
                "SELECT data FROM sleep_data WHERE date = ?", (date,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT data FROM sleep_data ORDER BY date"
            ).fetchall()
        return [DaySleep.model_validate_json(r["data"]) for r in rows]
    finally:
        con.close()


def load_hrv(date: str | None = None) -> list[DayHrv]:
    """Load HRV data, optionally filtered by date."""
    con = get_connection()
    try:
        if date:
            rows = con.execute(
                "SELECT data FROM hrv_data WHERE date = ?", (date,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT data FROM hrv_data ORDER BY date"
            ).fetchall()
        return [DayHrv.model_validate_json(r["data"]) for r in rows]
    finally:
        con.close()


def load_skin_temp(date: str | None = None) -> list[DaySkinTemp]:
    """Load skin temp data, optionally filtered by date."""
    con = get_connection()
    try:
        if date:
            rows = con.execute(
                "SELECT data FROM skin_temp_data WHERE date = ?", (date,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT data FROM skin_temp_data ORDER BY date"
            ).fetchall()
        return [DaySkinTemp.model_validate_json(r["data"]) for r in rows]
    finally:
        con.close()


def load_available_days() -> list[str]:
    """Load all dates that have data in the DB."""
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT date FROM daily_metrics ORDER BY date"
        ).fetchall()
        return [r["date"] for r in rows]
    finally:
        con.close()
