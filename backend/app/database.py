"""
SQLite persistence layer for Garmin Stats.

Write path (ingest):  FIT files → parser → stats → SQLite
Read path (API):      SQLite → reconstruct Pydantic models → API response
"""

import hashlib
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from . import cache
from .models import (
    DailyMetric,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    IngestResult,
    IngestStatus,
    PeriodSummary,
)
from .parser import get_files_by_day, parse_all_days
from .stats import compute_daily_aggregates

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent

DB_PATH = Path(os.environ.get(
    "GARMIN_DB_PATH",
    str(_PROJECT_ROOT / "storage" / "garmin_stats.db"),
))

DATA_DIR = Path(os.environ.get(
    "GARMIN_DATA_DIR",
    str(_PROJECT_ROOT / "data"),
))

_ingest_lock = threading.Lock()

_VALID_TABLES = frozenset({
    "wellness_data", "sleep_data", "hrv_data",
    "skin_temp_data", "daily_metrics", "ingest_meta",
})


# ---------------------------------------------------------------------------
# Schema & connection
# ---------------------------------------------------------------------------

_COLS_3 = "date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS wellness_data  ({_COLS_3});
CREATE TABLE IF NOT EXISTS sleep_data     ({_COLS_3});
CREATE TABLE IF NOT EXISTS hrv_data       ({_COLS_3});
CREATE TABLE IF NOT EXISTS skin_temp_data ({_COLS_3});
CREATE TABLE IF NOT EXISTS daily_metrics  ({_COLS_3});
CREATE TABLE IF NOT EXISTS ingest_meta    (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@contextmanager
def _connect():
    """Yield a sqlite3 connection with Row factory; close on exit."""
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they don't exist. Enable WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as con:
        con.executescript(_SCHEMA)
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

def compute_data_fingerprint(data_dir: Path) -> str:
    """SHA-256 of FIT file paths + size + modified time."""
    if not data_dir.exists():
        return hashlib.sha256(b"").hexdigest()

    parts: list[str] = []
    for fit_file in sorted(data_dir.rglob("*.fit")):
        stat = fit_file.stat()
        rel = fit_file.relative_to(data_dir)
        parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _get_meta(key: str) -> str | None:
    """Read a single metadata value."""
    with _connect() as con:
        row = con.execute(
            "SELECT value FROM ingest_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def _count_rows(table: str) -> int:
    """Count rows in a table (validated against whitelist)."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    with _connect() as con:
        row = con.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
        return row["cnt"]


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

        now = datetime.now(UTC).isoformat()
        upsert = "INSERT OR REPLACE INTO {} (date, data, updated_at) VALUES (?, ?, ?)"
        with _connect() as con, con:
            _delete_stale_day_rows(con, [d.date for d in all_days])

            # Per-day data
            for day in all_days:
                con.execute(
                    upsert.format("wellness_data"),
                    (day.date, day.wellness.model_dump_json(), now),
                )
                con.execute(
                    upsert.format("sleep_data"),
                    (day.date, day.sleep.model_dump_json(), now),
                )
                con.execute(
                    upsert.format("hrv_data"),
                    (day.date, day.hrv.model_dump_json(), now),
                )
                con.execute(
                    upsert.format("skin_temp_data"),
                    (day.date, day.skin_temp.model_dump_json(), now),
                )

            # Daily aggregates
            for metric in agg.daily:
                con.execute(
                    upsert.format("daily_metrics"),
                    (metric.date, metric.model_dump_json(), now),
                )

            # Period summary
            meta_upsert = (
                "INSERT OR REPLACE INTO ingest_meta"
                " (key, value) VALUES (?, ?)"
            )
            if agg.period:
                con.execute(
                    meta_upsert,
                    ("period_summary", agg.period.model_dump_json()),
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
                con.execute(meta_upsert, (k, v))

        cache.invalidate()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info("Ingested %d days in %d ms", len(all_days), duration_ms)
        return IngestResult(days_ingested=len(all_days), duration_ms=duration_ms)
    finally:
        _ingest_lock.release()


def _delete_stale_day_rows(con: sqlite3.Connection, parsed_dates: list[str]) -> None:
    """Delete DB rows for dates no longer present in parsed input."""
    per_day_tables = (
        "wellness_data",
        "sleep_data",
        "hrv_data",
        "skin_temp_data",
        "daily_metrics",
    )
    if not parsed_dates:
        for table in per_day_tables:
            con.execute(f"DELETE FROM {table}")
        return

    placeholders = ", ".join("?" for _ in parsed_dates)
    for table in per_day_tables:
        con.execute(
            f"DELETE FROM {table} WHERE date NOT IN ({placeholders})",
            parsed_dates,
        )


def is_db_empty() -> bool:
    """Check if the DB has any ingested data."""
    return _count_rows("daily_metrics") == 0


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------

def _load_day_table[M](
    table: str,
    model: type[M],
    cache_key: str,
    date: str | None = None,
) -> list[M]:
    """Generic loader for per-day data tables with caching.

    All-days results are cached.  Per-date queries filter from the warm
    all-days cache when available, falling back to a direct DB query.
    """
    if date is not None:
        all_cached = cache.get(cache_key)
        if all_cached is not None:
            return [item for item in all_cached if item.date == date]  # type: ignore[union-attr]
        with _connect() as con:
            rows = con.execute(
                f"SELECT data FROM {table} WHERE date = ?", (date,)  # noqa: S608
            ).fetchall()
        return [model.model_validate_json(r["data"]) for r in rows]  # type: ignore[union-attr]
    # All-days path with caching
    hit = cache.get(cache_key)
    if hit is not None:
        return hit
    gen = cache.generation()
    with _connect() as con:
        rows = con.execute(
            f"SELECT data FROM {table} ORDER BY date"  # noqa: S608
        ).fetchall()
    result = [model.model_validate_json(r["data"]) for r in rows]  # type: ignore[union-attr]
    cache.put(cache_key, result, gen)
    return result


def load_daily_metrics() -> list[DailyMetric]:
    """Load all daily metrics from DB (cached until next ingest)."""
    return cache.cached(cache.DAILY_METRICS, _fetch_daily_metrics)


def _fetch_daily_metrics() -> list[DailyMetric]:
    with _connect() as con:
        rows = con.execute(
            "SELECT data FROM daily_metrics ORDER BY date"
        ).fetchall()
    return [DailyMetric.model_validate_json(r["data"]) for r in rows]


def load_wellness(date: str | None = None) -> list[DayWellness]:
    """Load wellness data, optionally filtered by date."""
    return _load_day_table("wellness_data", DayWellness, cache.WELLNESS_ALL, date)


def load_sleep(date: str | None = None) -> list[DaySleep]:
    """Load sleep data, optionally filtered by date."""
    return _load_day_table("sleep_data", DaySleep, cache.SLEEP_ALL, date)


def load_hrv(date: str | None = None) -> list[DayHrv]:
    """Load HRV data, optionally filtered by date."""
    return _load_day_table("hrv_data", DayHrv, cache.HRV_ALL, date)


def load_skin_temp(date: str | None = None) -> list[DaySkinTemp]:
    """Load skin temp data, optionally filtered by date."""
    return _load_day_table("skin_temp_data", DaySkinTemp, cache.SKIN_TEMP_ALL, date)


def load_period_summary() -> PeriodSummary | None:
    """Load the precomputed period summary from DB (cached until next ingest)."""
    hit = cache.get(cache.PERIOD_SUMMARY)
    if hit is not None:
        return hit
    gen = cache.generation()
    raw = _get_meta("period_summary")
    if raw is None:
        return None
    result = PeriodSummary.model_validate_json(raw)
    cache.put(cache.PERIOD_SUMMARY, result, gen)
    return result


def load_available_days() -> list[str]:
    """Load all dates that have data in the DB (cached until next ingest)."""
    return cache.cached(cache.AVAILABLE_DAYS, _fetch_available_days)


def _fetch_available_days() -> list[str]:
    with _connect() as con:
        rows = con.execute(
            "SELECT date FROM daily_metrics ORDER BY date"
        ).fetchall()
    return [r["date"] for r in rows]
