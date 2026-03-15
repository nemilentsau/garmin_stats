"""
SQLite persistence layer for Garmin Stats.

Write path (ingest):  FIT files → parser → stats → SQLite
Read path (API):      SQLite → reconstruct Pydantic models → API response
"""

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from ..models import (
    DEFAULT_PROFILE_ID,
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    ContextSnapshot,
    DailyCheckIn,
    DailyMetric,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    EvidenceCard,
    Experiment,
    ExperimentExposure,
    ExperimentReport,
    Goal,
    IngestResult,
    IngestStatus,
    Note,
    Plan,
    PlanItem,
    Program,
    ProgramVersion,
    Routine,
    RoutineEntry,
    UserProfile,
)
from ..parser import get_files_by_day, parse_all_days
from ..stats import compute_daily_aggregates
from . import cache

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

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
    "user_profile", "goals", "routines", "routine_entries",
    "daily_checkins", "notes", "experiments", "experiment_exposures",
    "experiment_reports", "plans", "plan_items", "assistant_threads",
    "assistant_messages", "assistant_runs", "context_snapshots",
    "evidence_cards", "programs", "program_versions",
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
CREATE INDEX IF NOT EXISTS idx_routine_entries_routine_date
    ON routine_entries (routine_id, entry_date);
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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _save_json_record(
    table: str,
    record_id: str,
    data_json: str,
    *,
    extra_columns: dict[str, str | None] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    """Store a JSON-backed record in one of the assistant foundation tables."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")

    extra_columns = extra_columns or {}
    updated_value = updated_at or _now_iso()

    with _connect() as con, con:
        existing_created_at: str | None = None
        if created_at is None:
            row = con.execute(
                f"SELECT created_at FROM {table} WHERE id = ?",  # noqa: S608
                (record_id,),
            ).fetchone()
            existing_created_at = row["created_at"] if row is not None else None

        created_value = created_at or existing_created_at or _now_iso()

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
) -> list[M]:
    """Load JSON-backed records with optional filtering."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")

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


def load_daily_checkins(date: str | None = None) -> list[DailyCheckIn]:
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "daily_checkins",
        DailyCheckIn,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, id",
    )


def save_note(note: Note) -> None:
    _save_json_record(
        "notes",
        note.id,
        note.model_dump_json(),
        extra_columns={"entry_date": note.date},
    )


def load_notes(date: str | None = None) -> list[Note]:
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "notes",
        Note,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, created_at, id",
    )


def experiment_exists(experiment_id: str) -> bool:
    return _record_exists("experiments", experiment_id)


def load_experiment(experiment_id: str) -> Experiment | None:
    return _load_json_record("experiments", Experiment, experiment_id)


def save_experiment(experiment: Experiment) -> None:
    _save_json_record("experiments", experiment.id, experiment.model_dump_json())


def load_experiments() -> list[Experiment]:
    return _load_json_records("experiments", Experiment)


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
    now = _now_iso()
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
