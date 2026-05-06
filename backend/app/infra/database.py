"""
SQLite persistence layer for Garmin Stats.

Write path (ingest):  FIT files → parser → stats → SQLite
Read path (API):      SQLite → reconstruct Pydantic models → API response
"""

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from ..core.config import get_app_config
from ..domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
)
from ..domains.garmin_analytics.application.daily_aggregates import (
    compute_daily_aggregates,
)
from ..domains.garmin_sync.contracts import IngestResult, IngestStatus
from ..models import (
    DEFAULT_PROFILE_ID,
    AssistantArtifact,
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    CardLog,
    CardOverride,
    CardTemplate,
    ContextSnapshot,
    DailyCheckIn,
    DailyMetric,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    EvidenceCard,
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
    ExperimentReport,
    Goal,
    Note,
    Plan,
    PlanItem,
    Program,
    ProgramVersion,
    Routine,
    RoutineAssignment,
    RoutineEntry,
    RoutineSchedule,
    UserProfile,
)
from ..parser import get_files_by_day, parse_all_days, parse_day
from ..utils.timeutil import now_iso
from . import cache
from .sqlite import DB_PATH, connect

log = logging.getLogger(__name__)

_APP_CONFIG = get_app_config()

DATA_DIR = _APP_CONFIG.data_dir

_ingest_lock = threading.Lock()
_ALIAS_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_VALID_TABLES = frozenset({
    "wellness_data", "sleep_data", "hrv_data",
    "skin_temp_data", "daily_metrics", "ingest_meta",
    "user_profile", "goals", "routines", "routine_entries",
    "daily_checkins", "notes", "experiments", "experiment_exposures",
    "experiment_reports", "plans", "plan_items", "assistant_threads",
    "assistant_messages", "assistant_runs", "context_snapshots",
    "assistant_evidence_bundles", "assistant_memory_records",
    "evidence_cards", "programs", "program_versions",
    "assistant_artifacts", "card_templates", "routine_schedules",
    "routine_assignments", "card_logs", "card_overrides",
})


# ---------------------------------------------------------------------------
# Schema & connection
# ---------------------------------------------------------------------------

_COLS_3 = "date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL"
_JSON_COLS = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS wellness_data  ({_COLS_3});
CREATE TABLE IF NOT EXISTS sleep_data     ({_COLS_3});
CREATE TABLE IF NOT EXISTS hrv_data       ({_COLS_3});
CREATE TABLE IF NOT EXISTS skin_temp_data ({_COLS_3});
CREATE TABLE IF NOT EXISTS daily_metrics  ({_COLS_3});
CREATE TABLE IF NOT EXISTS ingest_meta    (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_profile   ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS goals          ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routines       ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS experiments    ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS plans          ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_threads ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS context_snapshots ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS evidence_cards ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_artifacts ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS card_templates ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routine_schedules ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routine_entries (
    id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_checkins (
    id TEXT PRIMARY KEY,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_exposures (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_reports (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_items (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    item_date TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_runs (
    id TEXT PRIMARY KEY,
    thread_id TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_evidence_bundles (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    user_message_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_memory_records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    entity_id TEXT,
    alias_text TEXT,
    alias_normalized TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS routine_assignments (
    id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL,
    card_template_id TEXT NOT NULL,
    assignment_date TEXT NOT NULL,
    slot TEXT NOT NULL,
    position INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_logs (
    id TEXT PRIMARY KEY,
    occurrence_key TEXT NOT NULL,
    log_date TEXT NOT NULL,
    card_template_id TEXT NOT NULL,
    assignment_id TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_overrides (
    id TEXT PRIMARY KEY,
    override_date TEXT NOT NULL,
    action TEXT NOT NULL,
    target_occurrence_key TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_routine_entries_routine_date
    ON routine_entries (routine_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_routine_assignments_routine_date
    ON routine_assignments (routine_id, assignment_date, slot, position);
CREATE INDEX IF NOT EXISTS idx_card_logs_date_occurrence
    ON card_logs (log_date, occurrence_key);
CREATE INDEX IF NOT EXISTS idx_card_overrides_date_action
    ON card_overrides (override_date, action);
CREATE INDEX IF NOT EXISTS idx_daily_checkins_entry_date
    ON daily_checkins (entry_date);
CREATE INDEX IF NOT EXISTS idx_notes_entry_date
    ON notes (entry_date);
CREATE INDEX IF NOT EXISTS idx_experiment_exposures_experiment_date
    ON experiment_exposures (experiment_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_experiment_reports_experiment_date
    ON experiment_reports (experiment_id, report_date);
CREATE INDEX IF NOT EXISTS idx_plan_items_plan_date
    ON plan_items (plan_id, item_date);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_thread_created
    ON assistant_messages (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assistant_runs_thread_created
    ON assistant_runs (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assistant_evidence_bundles_thread_created
    ON assistant_evidence_bundles (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assistant_memory_records_kind_created
    ON assistant_memory_records (kind, created_at);
CREATE TABLE IF NOT EXISTS experiment_analyses (
    experiment_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS programs ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS program_versions (
    program_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (program_id, version)
);
"""


def _connect():
    """Yield a sqlite3 connection with Row factory; close on exit."""
    return connect(str(DB_PATH))


def init_db() -> None:
    """Create tables if they don't exist. Enable WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as con:
        con.executescript(_SCHEMA)
        _ensure_assistant_memory_alias_lookup_columns(con)
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()


def _ensure_assistant_memory_alias_lookup_columns(con: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in con.execute("PRAGMA table_info(assistant_memory_records)").fetchall()
    }
    if "alias_normalized" not in columns:
        con.execute("ALTER TABLE assistant_memory_records ADD COLUMN alias_normalized TEXT")

    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_assistant_memory_records_kind_alias_normalized_created "
        "ON assistant_memory_records (kind, alias_normalized, created_at)"
    )

    rows = con.execute(
        "SELECT id, alias_text FROM assistant_memory_records "
        "WHERE alias_text IS NOT NULL AND (alias_normalized IS NULL OR alias_normalized = '')"
    ).fetchall()
    for row in rows:
        con.execute(
            "UPDATE assistant_memory_records SET alias_normalized = ? WHERE id = ?",
            (_normalize_alias_text(row["alias_text"]), row["id"]),
        )


def _normalize_alias_text(value: str | None) -> str | None:
    if value is None:
        return None
    tokens = _ALIAS_TOKEN_PATTERN.findall(value.lower())
    if not tokens:
        return None
    return " ".join(tokens)


def _save_json_record(
    table: str,
    record_id: str,
    data_json: str,
    *,
    extra_columns: dict[str, object | None] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    """Store a JSON-backed record in one of the assistant foundation tables."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")

    with _connect() as con, con:
        _save_json_record_in_connection(
            con,
            table,
            record_id,
            data_json,
            extra_columns=extra_columns,
            created_at=created_at,
            updated_at=updated_at,
        )


def _save_json_record_in_connection(
    con: sqlite3.Connection,
    table: str,
    record_id: str,
    data_json: str,
    *,
    extra_columns: dict[str, object | None] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    """Store a JSON-backed record using an existing transaction/connection."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")

    extra_columns = extra_columns or {}
    updated_value = updated_at or now_iso()
    existing_created_at: str | None = None
    if created_at is None:
        row = con.execute(
            f"SELECT created_at FROM {table} WHERE id = ?",  # noqa: S608
            (record_id,),
        ).fetchone()
        existing_created_at = row["created_at"] if row is not None else None

    created_value = created_at or existing_created_at or now_iso()

    columns = ["id", *extra_columns.keys(), "data", "created_at", "updated_at"]
    placeholders = ", ".join("?" for _ in columns)
    values = [record_id, *extra_columns.values(), data_json, created_value, updated_value]

    con.execute(
        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",  # noqa: S608
        values,
    )


def _model_from_row[M](model: type[M], row: sqlite3.Row) -> M:
    payload = json.loads(row["data"])
    for key in ("created_at", "updated_at"):
        if payload.get(key) is None and row[key] is not None:
            payload[key] = row[key]
    return model.model_validate(payload)  # type: ignore[union-attr]


def _record_exists(table: str, record_id: str) -> bool:
    """Check whether a record with the given id exists (without loading JSON)."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    with _connect() as con:
        row = con.execute(
            f"SELECT 1 FROM {table} WHERE id = ? LIMIT 1",  # noqa: S608
            (record_id,),
        ).fetchone()
    return row is not None


def _delete_json_record(table: str, record_id: str) -> None:
    """Delete a single JSON-backed record by id."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    with _connect() as con, con:
        con.execute(
            f"DELETE FROM {table} WHERE id = ?",  # noqa: S608
            (record_id,),
        )


def _load_json_record[M](
    table: str,
    model: type[M],
    record_id: str,
) -> M | None:
    """Load a single JSON-backed record by id."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")

    with _connect() as con:
        row = con.execute(
            f"SELECT data, created_at, updated_at FROM {table} WHERE id = ?",  # noqa: S608
            (record_id,),
        ).fetchone()
    if row is None:
        return None
    return _model_from_row(model, row)


def _load_json_records[M](
    table: str,
    model: type[M],
    *,
    where_sql: str = "",
    params: tuple[object, ...] = (),
    order_by: str = "created_at, id",
    last_n: int | None = None,
) -> list[M]:
    """Load JSON-backed records with optional filtering.

    When *last_n* is set the query returns only the last N rows (by
    *order_by*) while preserving ascending order in the result.
    """
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")

    if last_n is not None and last_n > 0:
        # Reverse each column in order_by for the inner DESC query.
        desc_cols = ", ".join(f"{col.strip()} DESC" for col in order_by.split(","))
        inner = f"SELECT * FROM {table}"  # noqa: S608
        if where_sql:
            inner += f" WHERE {where_sql}"  # noqa: S608
        inner += f" ORDER BY {desc_cols} LIMIT ?"  # noqa: S608
        query = (
            f"SELECT data, created_at, updated_at FROM ({inner}) "  # noqa: S608
            f"ORDER BY {order_by}"  # noqa: S608
        )
        with _connect() as con:
            rows = con.execute(query, (*params, last_n)).fetchall()
        return [_model_from_row(model, row) for row in rows]

    query = f"SELECT data, created_at, updated_at FROM {table}"  # noqa: S608
    if where_sql:
        query += f" WHERE {where_sql}"  # noqa: S608
    query += f" ORDER BY {order_by}"  # noqa: S608

    with _connect() as con:
        rows = con.execute(query, params).fetchall()
    return [_model_from_row(model, row) for row in rows]


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

            # Metadata
            meta_upsert = (
                "INSERT OR REPLACE INTO ingest_meta"
                " (key, value) VALUES (?, ?)"
            )
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


def ingest_dates(data_dir: Path, dates: list[str]) -> IngestResult:
    """Parse and upsert only the specified dates.

    Much faster than ingest_all when only a few days changed.
    """
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
            parse_day(d, files)
            for d, files in sorted(files_by_day.items())
            if d in date_set
        ]

        now = datetime.now(UTC).isoformat()
        upsert = "INSERT OR REPLACE INTO {} (date, data, updated_at) VALUES (?, ?, ?)"
        with _connect() as con, con:
            for day in parsed_days:
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

            for day in parsed_days:
                metric = compute_daily_aggregates([day]).daily[0]
                con.execute(
                    upsert.format("daily_metrics"),
                    (metric.date, metric.model_dump_json(), now),
                )

            # Update fingerprint so startup check stays in sync
            meta_upsert = (
                "INSERT OR REPLACE INTO ingest_meta"
                " (key, value) VALUES (?, ?)"
            )
            fingerprint = compute_data_fingerprint(data_dir)
            con.execute(meta_upsert, ("data_fingerprint", fingerprint))
            con.execute(meta_upsert, ("last_ingest_time", now))

        cache.invalidate()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info("Ingested %d days (incremental) in %d ms", len(parsed_days), duration_ms)
        return IngestResult(days_ingested=len(parsed_days), duration_ms=duration_ms)
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


def load_available_days() -> list[str]:
    """Load all dates that have data in the DB (cached until next ingest)."""
    return cache.cached(cache.AVAILABLE_DAYS, _fetch_available_days)


def _fetch_available_days() -> list[str]:
    with _connect() as con:
        rows = con.execute(
            "SELECT date FROM daily_metrics ORDER BY date"
        ).fetchall()
    return [r["date"] for r in rows]


# ---------------------------------------------------------------------------
# Health assistant foundation storage
# ---------------------------------------------------------------------------

def save_user_profile(profile: UserProfile) -> None:
    _save_json_record("user_profile", profile.id, profile.model_dump_json())


def load_user_profile(profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
    return _load_json_record("user_profile", UserProfile, profile_id)


def save_goal(goal: Goal) -> None:
    _save_json_record("goals", goal.id, goal.model_dump_json())


def load_goals() -> list[Goal]:
    return _load_json_records("goals", Goal)


def routine_exists(routine_id: str) -> bool:
    return _record_exists("routines", routine_id)


def save_routine(routine: Routine) -> None:
    _save_json_record("routines", routine.id, routine.model_dump_json())


def delete_routine(routine_id: str) -> None:
    _delete_json_record("routines", routine_id)


def load_routines() -> list[Routine]:
    return _load_json_records("routines", Routine)


def save_routine_entry(entry: RoutineEntry) -> None:
    _save_json_record(
        "routine_entries",
        entry.id,
        entry.model_dump_json(),
        extra_columns={
            "routine_id": entry.routine_id,
            "entry_date": entry.date,
        },
    )


def load_routine_entries(
    routine_id: str | None = None,
    date: str | None = None,
) -> list[RoutineEntry]:
    clauses: list[str] = []
    params: list[object] = []
    if routine_id is not None:
        clauses.append("routine_id = ?")
        params.append(routine_id)
    if date is not None:
        clauses.append("entry_date = ?")
        params.append(date)
    return _load_json_records(
        "routine_entries",
        RoutineEntry,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="entry_date, created_at, id",
    )


def save_daily_checkin(checkin: DailyCheckIn) -> None:
    _save_json_record(
        "daily_checkins",
        checkin.id,
        checkin.model_dump_json(),
        extra_columns={"entry_date": checkin.date},
    )


def load_daily_checkins(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[DailyCheckIn]:
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "daily_checkins",
        DailyCheckIn,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, id",
        last_n=last_n,
    )


def save_note(note: Note) -> None:
    _save_json_record(
        "notes",
        note.id,
        note.model_dump_json(),
        extra_columns={"entry_date": note.date},
    )


def load_notes(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[Note]:
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "notes",
        Note,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, created_at, id",
        last_n=last_n,
    )


def experiment_exists(experiment_id: str) -> bool:
    return _record_exists("experiments", experiment_id)


def load_experiment(experiment_id: str) -> Experiment | None:
    return _load_json_record("experiments", Experiment, experiment_id)


def save_experiment(experiment: Experiment) -> None:
    _save_json_record("experiments", experiment.id, experiment.model_dump_json())


def delete_experiment(experiment_id: str) -> None:
    _delete_json_record("experiments", experiment_id)


def load_experiments(
    *,
    statuses: tuple[str, ...] | None = None,
) -> list[Experiment]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if statuses is not None:
        placeholders = ", ".join("?" for _ in statuses)
        where_sql = f"json_extract(data, '$.status') IN ({placeholders})"
        params = statuses
    return _load_json_records("experiments", Experiment, where_sql=where_sql, params=params)


def save_experiment_exposure(exposure: ExperimentExposure) -> None:
    _save_json_record(
        "experiment_exposures",
        exposure.id,
        exposure.model_dump_json(),
        extra_columns={
            "experiment_id": exposure.experiment_id,
            "entry_date": exposure.date,
        },
    )


def replace_experiment_exposure_for_date(
    experiment_id: str,
    date: str,
    exposure: ExperimentExposure | None,
) -> None:
    """Replace the derived exposure row for one experiment-day.

    Manual same-day exposure rows are preserved and take precedence over any
    derived exposure the sync service would otherwise write.
    """
    auto_id = ExperimentExposure.auto_id(experiment_id, date)
    if exposure is not None and (
        exposure.experiment_id != experiment_id
        or exposure.date != date
        or exposure.id != auto_id
    ):
        raise ValueError("Exposure does not match experiment_id/date replacement target")

    with _connect() as con, con:
        manual_exists = con.execute(
            """
            SELECT 1
            FROM experiment_exposures
            WHERE experiment_id = ? AND entry_date = ? AND id != ?
            LIMIT 1
            """,
            (experiment_id, date, auto_id),
        ).fetchone() is not None
        con.execute("DELETE FROM experiment_exposures WHERE id = ?", (auto_id,))
        if exposure is None or manual_exists:
            return
        _save_json_record_in_connection(
            con,
            "experiment_exposures",
            exposure.id,
            exposure.model_dump_json(),
            extra_columns={
                "experiment_id": exposure.experiment_id,
                "entry_date": exposure.date,
            },
        )


def load_experiment_exposures(
    experiment_id: str | None = None,
    date: str | None = None,
) -> list[ExperimentExposure]:
    clauses: list[str] = []
    params: list[object] = []
    if experiment_id is not None:
        clauses.append("experiment_id = ?")
        params.append(experiment_id)
    if date is not None:
        clauses.append("entry_date = ?")
        params.append(date)
    return _load_json_records(
        "experiment_exposures",
        ExperimentExposure,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="entry_date, created_at, id",
    )


def save_experiment_report(report: ExperimentReport) -> None:
    _save_json_record(
        "experiment_reports",
        report.id,
        report.model_dump_json(),
        extra_columns={
            "experiment_id": report.experiment_id,
            "report_date": report.report_date,
        },
    )


def load_experiment_reports(experiment_id: str | None = None) -> list[ExperimentReport]:
    where_sql = "experiment_id = ?" if experiment_id is not None else ""
    params = (experiment_id,) if experiment_id is not None else ()
    return _load_json_records(
        "experiment_reports",
        ExperimentReport,
        where_sql=where_sql,
        params=params,
        order_by="report_date, created_at, id",
    )


def save_experiment_analysis(experiment_id: str, analysis: ExperimentAnalysis) -> None:
    """Upsert computed analysis for an experiment (keyed by experiment_id)."""
    now = now_iso()
    data_json = analysis.model_dump_json()
    with _connect() as con, con:
        con.execute(
            "INSERT OR REPLACE INTO experiment_analyses "
            "(experiment_id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (experiment_id, data_json, now, now),
        )


def delete_experiment_analysis(experiment_id: str) -> None:
    """Delete any persisted analysis for an experiment."""
    with _connect() as con, con:
        con.execute(
            "DELETE FROM experiment_analyses WHERE experiment_id = ?",
            (experiment_id,),
        )


def load_experiment_analysis(experiment_id: str) -> ExperimentAnalysis | None:
    """Load the latest computed analysis for an experiment."""
    with _connect() as con:
        row = con.execute(
            "SELECT data FROM experiment_analyses WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    if row is None:
        return None
    return ExperimentAnalysis.model_validate_json(row["data"])


def load_all_experiment_analyses() -> dict[str, ExperimentAnalysis]:
    """Load all experiment analyses, keyed by experiment_id."""
    with _connect() as con:
        rows = con.execute("SELECT experiment_id, data FROM experiment_analyses").fetchall()
    return {
        row["experiment_id"]: ExperimentAnalysis.model_validate_json(row["data"])
        for row in rows
    }


def save_plan(plan: Plan) -> None:
    _save_json_record("plans", plan.id, plan.model_dump_json())


def load_plans() -> list[Plan]:
    return _load_json_records("plans", Plan)


def save_plan_item(item: PlanItem) -> None:
    _save_json_record(
        "plan_items",
        item.id,
        item.model_dump_json(),
        extra_columns={
            "plan_id": item.plan_id,
            "item_date": item.date,
        },
    )


def load_plan_items(plan_id: str | None = None) -> list[PlanItem]:
    where_sql = "plan_id = ?" if plan_id is not None else ""
    params = (plan_id,) if plan_id is not None else ()
    return _load_json_records(
        "plan_items",
        PlanItem,
        where_sql=where_sql,
        params=params,
        order_by="item_date, created_at, id",
    )


def create_assistant_thread(thread: AssistantThread) -> None:
    created_at = thread.created_at or now_iso()
    payload = thread.model_copy(update={"created_at": created_at}).model_dump_json()
    with _connect() as con, con:
        try:
            con.execute(
                (
                    "INSERT INTO assistant_threads "
                    "(id, data, created_at, updated_at) VALUES (?, ?, ?, ?)"
                ),
                (thread.id, payload, created_at, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Assistant thread {thread.id} already exists") from exc


def save_assistant_thread(thread: AssistantThread) -> None:
    _save_json_record("assistant_threads", thread.id, thread.model_dump_json())


def load_assistant_thread(thread_id: str) -> AssistantThread | None:
    return _load_json_record("assistant_threads", AssistantThread, thread_id)


def load_assistant_threads() -> list[AssistantThread]:
    return _load_json_records("assistant_threads", AssistantThread)


def save_assistant_message(message: AssistantMessage) -> None:
    _save_json_record(
        "assistant_messages",
        message.id,
        message.model_dump_json(),
        extra_columns={"thread_id": message.thread_id},
        created_at=message.created_at,
    )


def load_assistant_messages(thread_id: str) -> list[AssistantMessage]:
    return _load_json_records(
        "assistant_messages",
        AssistantMessage,
        where_sql="thread_id = ?",
        params=(thread_id,),
        order_by="created_at, id",
    )


def save_assistant_run(run: AssistantRun) -> None:
    _save_json_record(
        "assistant_runs",
        run.id,
        run.model_dump_json(),
        extra_columns={"thread_id": run.thread_id},
        created_at=run.started_at,
        updated_at=run.finished_at or run.started_at,
    )


def finalize_assistant_reply(
    *,
    assistant_message: AssistantMessage,
    updated_thread: AssistantThread,
    completed_run: AssistantRun,
    memory_record: AssistantMemoryRecord | None = None,
) -> None:
    """Persist assistant reply + thread metadata + completed run atomically."""
    with _connect() as con, con:
        _save_json_record_in_connection(
            con,
            "assistant_messages",
            assistant_message.id,
            assistant_message.model_dump_json(),
            extra_columns={"thread_id": assistant_message.thread_id},
            created_at=assistant_message.created_at,
        )
        _save_json_record_in_connection(
            con,
            "assistant_threads",
            updated_thread.id,
            updated_thread.model_dump_json(),
        )
        _save_json_record_in_connection(
            con,
            "assistant_runs",
            completed_run.id,
            completed_run.model_dump_json(),
            extra_columns={"thread_id": completed_run.thread_id},
            created_at=completed_run.started_at,
            updated_at=completed_run.finished_at or completed_run.started_at,
        )
        if memory_record is not None:
            _save_json_record_in_connection(
                con,
                "assistant_memory_records",
                memory_record.id,
                memory_record.model_dump_json(),
                extra_columns={
                    "kind": memory_record.kind,
                    "entity_id": memory_record.entity_id,
                    "alias_text": memory_record.alias_text,
                    "alias_normalized": _normalize_alias_text(memory_record.alias_text),
                },
                created_at=memory_record.created_at,
                updated_at=memory_record.updated_at or memory_record.created_at,
            )


def load_assistant_runs(thread_id: str | None = None) -> list[AssistantRun]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _load_json_records(
        "assistant_runs",
        AssistantRun,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
    )


def save_assistant_evidence_bundle(bundle: AssistantEvidenceBundle) -> None:
    _save_json_record(
        "assistant_evidence_bundles",
        bundle.id,
        bundle.model_dump_json(),
        extra_columns={
            "thread_id": bundle.thread_id,
            "user_message_id": bundle.user_message_id,
            "intent": bundle.intent,
        },
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
    )


def load_assistant_evidence_bundles(
    thread_id: str | None = None,
    *,
    last_n: int | None = None,
) -> list[AssistantEvidenceBundle]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _load_json_records(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
        last_n=last_n,
    )


def save_assistant_memory_record(record: AssistantMemoryRecord) -> None:
    _save_json_record(
        "assistant_memory_records",
        record.id,
        record.model_dump_json(),
        extra_columns={
            "kind": record.kind,
            "entity_id": record.entity_id,
            "alias_text": record.alias_text,
            "alias_normalized": _normalize_alias_text(record.alias_text),
        },
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def load_assistant_memory_records(
    kind: str | None = None,
    *,
    last_n: int | None = None,
    alias_candidates: tuple[str, ...] | None = None,
) -> list[AssistantMemoryRecord]:
    clauses: list[str] = []
    params: list[object] = []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)

    normalized_candidates = tuple(
        normalized
        for normalized in (
            _normalize_alias_text(candidate) for candidate in (alias_candidates or ())
        )
        if normalized is not None
    )
    if alias_candidates is not None:
        if not normalized_candidates:
            return []
        placeholders = ", ".join("?" for _ in normalized_candidates)
        clauses.append(f"alias_normalized IN ({placeholders})")
        params.extend(normalized_candidates)

    return _load_json_records(
        "assistant_memory_records",
        AssistantMemoryRecord,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="created_at, id",
        last_n=last_n,
    )


def save_context_snapshot(snapshot: ContextSnapshot) -> None:
    _save_json_record(
        "context_snapshots",
        snapshot.id,
        snapshot.model_dump_json(),
        created_at=snapshot.created_at,
    )


def load_context_snapshot(snapshot_id: str) -> ContextSnapshot | None:
    return _load_json_record("context_snapshots", ContextSnapshot, snapshot_id)


def load_context_snapshots() -> list[ContextSnapshot]:
    return _load_json_records("context_snapshots", ContextSnapshot)


def save_evidence_card(card: EvidenceCard) -> None:
    _save_json_record("evidence_cards", card.id, card.model_dump_json())


def load_evidence_cards() -> list[EvidenceCard]:
    return _load_json_records("evidence_cards", EvidenceCard)


# ---------------------------------------------------------------------------
# Training spec platform storage
# ---------------------------------------------------------------------------


def save_assistant_artifact(artifact: AssistantArtifact) -> None:
    _save_json_record(
        "assistant_artifacts",
        artifact.id,
        artifact.model_dump_json(),
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


def save_assistant_artifacts_batch(artifacts: list[AssistantArtifact]) -> None:
    """Persist a batch of assistant artifacts atomically."""
    with _connect() as con, con:
        for artifact in artifacts:
            con.execute(
                (
                    "INSERT OR REPLACE INTO assistant_artifacts "
                    "(id, data, created_at, updated_at) VALUES (?, ?, ?, ?)"
                ),
                (
                    artifact.id,
                    artifact.model_dump_json(),
                    artifact.created_at or now_iso(),
                    artifact.updated_at or now_iso(),
                ),
            )


def load_assistant_artifact(artifact_id: str) -> AssistantArtifact | None:
    return _load_json_record("assistant_artifacts", AssistantArtifact, artifact_id)


def load_assistant_artifacts(
    *,
    kind: str | None = None,
    status: str | None = None,
) -> list[AssistantArtifact]:
    clauses: list[str] = []
    params: list[object] = []
    if kind is not None:
        clauses.append("json_extract(data, '$.kind') = ?")
        params.append(kind)
    if status is not None:
        clauses.append("json_extract(data, '$.status') = ?")
        params.append(status)
    return _load_json_records(
        "assistant_artifacts",
        AssistantArtifact,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="created_at DESC, id",
    )


def load_assistant_artifact_by_payload_id(
    kind: str,
    payload_id: str,
    statuses: tuple[str, ...],
) -> AssistantArtifact | None:
    """Find an artifact whose payload_json.id matches, filtered by kind+statuses."""
    if not statuses:
        return None
    placeholders = ", ".join("?" for _ in statuses)
    rows_query = (
        "SELECT data, created_at, updated_at FROM assistant_artifacts "
        f"WHERE json_extract(data, '$.kind') = ? "
        f"AND json_extract(data, '$.payload_json.id') = ? "
        f"AND json_extract(data, '$.status') IN ({placeholders}) "
        "ORDER BY created_at DESC LIMIT 1"
    )
    with _connect() as con:
        row = con.execute(rows_query, (kind, payload_id, *statuses)).fetchone()
    if row is None:
        return None
    return _model_from_row(AssistantArtifact, row)


def load_max_artifact_revision(kind: str, id_prefix: str) -> int:
    """Return the highest revision number for artifacts matching a bundle id prefix."""
    query = (
        "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) AS max_rev "
        "FROM assistant_artifacts "
        "WHERE json_extract(data, '$.kind') = ? AND id LIKE ? || '%'"
    )
    prefix_len = len(id_prefix) + 1  # +1 for 1-based SUBSTR
    with _connect() as con:
        row = con.execute(query, (prefix_len, kind, id_prefix)).fetchone()
    if row is None or row["max_rev"] is None:
        return 0
    return int(row["max_rev"])


def save_card_template(card: CardTemplate) -> None:
    _save_json_record("card_templates", card.id, card.model_dump_json())


def load_card_template(card_id: str) -> CardTemplate | None:
    return _load_json_record("card_templates", CardTemplate, card_id)


def load_card_templates(status: str | None = None) -> list[CardTemplate]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _load_json_records(
        "card_templates",
        CardTemplate,
        where_sql=where_sql,
        params=params,
    )


def save_routine_schedule(routine: RoutineSchedule) -> None:
    _save_json_record("routine_schedules", routine.id, routine.model_dump_json())


def load_routine_schedule(routine_id: str) -> RoutineSchedule | None:
    return _load_json_record("routine_schedules", RoutineSchedule, routine_id)


def load_routine_schedules(status: str | None = None) -> list[RoutineSchedule]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _load_json_records(
        "routine_schedules",
        RoutineSchedule,
        where_sql=where_sql,
        params=params,
    )


def delete_routine_assignments(routine_id: str) -> None:
    with _connect() as con, con:
        con.execute("DELETE FROM routine_assignments WHERE routine_id = ?", (routine_id,))


def save_routine_assignment(assignment: RoutineAssignment) -> None:
    _save_json_record(
        "routine_assignments",
        assignment.id,
        assignment.model_dump_json(),
        extra_columns={
            "routine_id": assignment.routine_id,
            "card_template_id": assignment.card_template_id,
            "assignment_date": assignment.date,
            "slot": assignment.slot,
            "position": assignment.position,
        },
    )


def _validate_routine_assignment_ids(
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    if any(assignment.routine_id != routine_id for assignment in assignments):
        raise ValueError("All assignments must match the provided routine_id")


def _guard_assignment_ownership(
    con: sqlite3.Connection,
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    if not assignments:
        return

    placeholders = ", ".join("?" for _ in assignments)
    rows = con.execute(
        "SELECT id, routine_id FROM routine_assignments WHERE id IN "
        f"({placeholders})",
        [assignment.id for assignment in assignments],
    ).fetchall()
    existing_routine_ids = {str(row["id"]): str(row["routine_id"]) for row in rows}
    for assignment in assignments:
        owner_routine_id = existing_routine_ids.get(assignment.id)
        if owner_routine_id is not None and owner_routine_id != routine_id:
            raise ValueError(
                f"Assignment id '{assignment.id}' already belongs to routine "
                f"{owner_routine_id}"
            )


def _replace_routine_assignments_in_connection(
    con: sqlite3.Connection,
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    _validate_routine_assignment_ids(routine_id, assignments)
    _guard_assignment_ownership(con, routine_id, assignments)
    con.execute("DELETE FROM routine_assignments WHERE routine_id = ?", (routine_id,))
    for assignment in assignments:
        _save_json_record_in_connection(
            con,
            "routine_assignments",
            assignment.id,
            assignment.model_dump_json(),
            extra_columns={
                "routine_id": assignment.routine_id,
                "card_template_id": assignment.card_template_id,
                "assignment_date": assignment.date,
                "slot": assignment.slot,
                "position": assignment.position,
            },
        )


def save_routine_schedule_with_assignments(
    routine: RoutineSchedule,
    assignments: list[RoutineAssignment],
) -> None:
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _save_json_record_in_connection(
                con,
                "routine_schedules",
                routine.id,
                routine.model_dump_json(),
            )
            _replace_routine_assignments_in_connection(con, routine.id, assignments)
        except Exception:
            con.rollback()
            raise
        else:
            con.commit()


def replace_routine_assignments(
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _replace_routine_assignments_in_connection(con, routine_id, assignments)
        except Exception:
            con.rollback()
            raise
        else:
            con.commit()


def load_routine_assignments(routine_id: str | None = None) -> list[RoutineAssignment]:
    where_sql = "routine_id = ?" if routine_id is not None else ""
    params = (routine_id,) if routine_id is not None else ()
    return _load_json_records(
        "routine_assignments",
        RoutineAssignment,
        where_sql=where_sql,
        params=params,
        order_by="routine_id, assignment_date, slot, position, id",
    )


def save_card_log(log: CardLog) -> None:
    _save_json_record(
        "card_logs",
        log.id,
        log.model_dump_json(),
        extra_columns={
            "occurrence_key": log.occurrence_key,
            "log_date": log.date,
            "card_template_id": log.card_template_id,
            "assignment_id": log.assignment_id,
        },
    )


def load_card_logs(date: str | None = None) -> list[CardLog]:
    where_sql = "log_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "card_logs",
        CardLog,
        where_sql=where_sql,
        params=params,
        order_by="log_date, created_at, id",
    )


def load_card_logs_range(start_date: str, end_date: str) -> list[CardLog]:
    """Load card logs for a date range (inclusive on both ends)."""
    return _load_json_records(
        "card_logs",
        CardLog,
        where_sql="log_date >= ? AND log_date <= ?",
        params=(start_date, end_date),
        order_by="log_date, created_at, id",
    )


def save_card_override(override: CardOverride) -> None:
    _save_json_record(
        "card_overrides",
        override.id,
        override.model_dump_json(),
        extra_columns={
            "override_date": override.date,
            "action": override.action,
            "target_occurrence_key": override.target_occurrence_key,
        },
    )


def load_card_overrides(date: str | None = None) -> list[CardOverride]:
    where_sql = "override_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "card_overrides",
        CardOverride,
        where_sql=where_sql,
        params=params,
        order_by="override_date, created_at, id",
    )


def load_card_overrides_range(
    start_date: str,
    end_date: str,
) -> list[CardOverride]:
    """Load card overrides for a contiguous date range (inclusive)."""
    return _load_json_records(
        "card_overrides",
        CardOverride,
        where_sql="override_date >= ? AND override_date <= ?",
        params=(start_date, end_date),
        order_by="override_date, created_at, id",
    )


# ---------------------------------------------------------------------------
# Program storage
# ---------------------------------------------------------------------------


def save_program(program: Program) -> None:
    _save_json_record("programs", program.id, program.model_dump_json())


def load_program(program_id: str) -> Program | None:
    return _load_json_record("programs", Program, program_id)


def load_programs(status: str | None = None) -> list[Program]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _load_json_records(
        "programs",
        Program,
        where_sql=where_sql,
        params=params,
    )


def save_program_version(version: ProgramVersion) -> None:
    now = now_iso()
    data_json = version.model_dump_json()
    with _connect() as con, con:
        con.execute(
            "INSERT OR REPLACE INTO program_versions "
            "(program_id, version, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (version.program_id, version.version, data_json, now, now),
        )


def load_program_versions(program_id: str) -> list[ProgramVersion]:
    with _connect() as con:
        rows = con.execute(
            "SELECT data, created_at, updated_at FROM program_versions "
            "WHERE program_id = ? ORDER BY version",
            (program_id,),
        ).fetchall()
    return [_model_from_row(ProgramVersion, row) for row in rows]


def delete_program(program_id: str) -> None:
    with _connect() as con, con:
        con.execute("DELETE FROM programs WHERE id = ?", (program_id,))
        con.execute(
            "DELETE FROM program_versions WHERE program_id = ?",
            (program_id,),
        )


def save_program_import(
    *,
    program: Program,
    previous_version: ProgramVersion | None,
) -> None:
    """Persist a placeholder program import and optional previous version atomically."""
    timestamp = now_iso()
    with _connect() as con, con:
        if previous_version is not None:
            con.execute(
                "INSERT OR REPLACE INTO program_versions "
                "(program_id, version, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    previous_version.program_id,
                    previous_version.version,
                    previous_version.model_dump_json(),
                    timestamp,
                    timestamp,
                ),
            )

        _save_json_record_in_connection(
            con,
            "programs",
            program.id,
            program.model_dump_json(),
        )
