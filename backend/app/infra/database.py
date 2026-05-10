"""
SQLite persistence layer for Garmin Stats.

Write path (ingest):  FIT files → parser → Garmin health daily metrics → SQLite
Read path (API):      SQLite → reconstruct Pydantic models → API response
"""

import hashlib
import logging
import re
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from ..core.config import get_app_config
from ..core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    Goal,
    UserProfile,
)
from ..domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
)
from ..domains.assistant.contracts import (
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    ContextSnapshot,
    EvidenceCard,
    Plan,
    PlanItem,
)
from ..domains.garmin_health.contracts import DayData
from ..domains.garmin_health.domain.daily import (
    compute_daily_metrics,
)
from ..domains.garmin_sync.contracts import IngestResult, IngestStatus
from ..domains.journal.contracts import DailyCheckIn, Note
from ..domains.programs.contracts import Program, ProgramVersion
from ..parser import get_files_by_day, parse_all_days, parse_day
from ..utils.timeutil import now_iso
from . import cache
from .jsonstore import JsonStore
from .jsonstore import model_from_row as _model_from_row
from .sqlite import DB_PATH, connect

log = logging.getLogger(__name__)

_APP_CONFIG = get_app_config()

DATA_DIR = _APP_CONFIG.data_dir

_ingest_lock = threading.Lock()
_ALIAS_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_RAW_DAY_TABLES = (
    "wellness_data",
    "sleep_data",
    "hrv_data",
    "skin_temp_data",
)
_PER_DAY_TABLES = (*_RAW_DAY_TABLES, "daily_metrics")

_VALID_TABLES = frozenset({
    "wellness_data", "sleep_data", "hrv_data",
    "skin_temp_data", "daily_metrics", "ingest_meta",
    "user_profile", "goals",
    "daily_checkins", "notes", "experiments", "experiment_exposures",
    "experiment_reports", "plans", "plan_items", "assistant_threads",
    "assistant_messages", "assistant_runs", "context_snapshots",
    "assistant_evidence_bundles", "assistant_memory_records",
    "evidence_cards", "programs", "program_versions",
    "assistant_artifacts",
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
CREATE TABLE IF NOT EXISTS experiments    ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS plans          ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_threads ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS context_snapshots ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS evidence_cards ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_artifacts ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS card_templates ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routine_schedules ({_JSON_COLS});
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


_STORE = JsonStore(_VALID_TABLES)


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


def _table_dates(con: sqlite3.Connection, table: str) -> set[str]:
    if table not in _VALID_TABLES:
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
    with _connect() as con:
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

        now = datetime.now(UTC).isoformat()
        with _connect() as con, con:
            _delete_stale_day_rows(con, [d.date for d in all_days])
            _upsert_parsed_day_data(con, all_days, now)

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
        with _connect() as con, con:
            _upsert_parsed_day_data(con, parsed_days, now)

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


def is_db_empty() -> bool:
    """Check if the DB has any ingested data."""
    return _count_rows("daily_metrics") == 0


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
    _STORE.save("user_profile", profile.id, profile.model_dump_json())


def load_user_profile(profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
    return _STORE.load("user_profile", UserProfile, profile_id)


def save_goal(goal: Goal) -> None:
    _STORE.save("goals", goal.id, goal.model_dump_json())


def load_goals() -> list[Goal]:
    return _STORE.load_many("goals", Goal)


def save_daily_checkin(checkin: DailyCheckIn) -> None:
    _STORE.save(
        "daily_checkins",
        checkin.id,
        checkin.model_dump_json(),
        extra_columns={"entry_date": checkin.date},
    )
    cache.evict(cache.DAILY_CHECKINS)


def load_daily_checkins(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[DailyCheckIn]:
    if date is None and last_n is None:
        return cache.cached(cache.DAILY_CHECKINS, _fetch_all_daily_checkins)
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _STORE.load_many(
        "daily_checkins",
        DailyCheckIn,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, id",
        last_n=last_n,
    )


def _fetch_all_daily_checkins() -> list[DailyCheckIn]:
    return _STORE.load_many(
        "daily_checkins",
        DailyCheckIn,
        order_by="entry_date, id",
    )


def save_note(note: Note) -> None:
    _STORE.save(
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
    return _STORE.load_many(
        "notes",
        Note,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, created_at, id",
        last_n=last_n,
    )


def save_plan(plan: Plan) -> None:
    _STORE.save("plans", plan.id, plan.model_dump_json())


def load_plans() -> list[Plan]:
    return _STORE.load_many("plans", Plan)


def save_plan_item(item: PlanItem) -> None:
    _STORE.save(
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
    return _STORE.load_many(
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
    _STORE.save("assistant_threads", thread.id, thread.model_dump_json())


def load_assistant_thread(thread_id: str) -> AssistantThread | None:
    return _STORE.load("assistant_threads", AssistantThread, thread_id)


def load_assistant_threads() -> list[AssistantThread]:
    return _STORE.load_many("assistant_threads", AssistantThread)


def save_assistant_message(message: AssistantMessage) -> None:
    _STORE.save(
        "assistant_messages",
        message.id,
        message.model_dump_json(),
        extra_columns={"thread_id": message.thread_id},
        created_at=message.created_at,
    )


def load_assistant_messages(thread_id: str) -> list[AssistantMessage]:
    return _STORE.load_many(
        "assistant_messages",
        AssistantMessage,
        where_sql="thread_id = ?",
        params=(thread_id,),
        order_by="created_at, id",
    )


def save_assistant_run(run: AssistantRun) -> None:
    _STORE.save(
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
        _STORE.save_in_connection(
            con,
            "assistant_messages",
            assistant_message.id,
            assistant_message.model_dump_json(),
            extra_columns={"thread_id": assistant_message.thread_id},
            created_at=assistant_message.created_at,
        )
        _STORE.save_in_connection(
            con,
            "assistant_threads",
            updated_thread.id,
            updated_thread.model_dump_json(),
        )
        _STORE.save_in_connection(
            con,
            "assistant_runs",
            completed_run.id,
            completed_run.model_dump_json(),
            extra_columns={"thread_id": completed_run.thread_id},
            created_at=completed_run.started_at,
            updated_at=completed_run.finished_at or completed_run.started_at,
        )
        if memory_record is not None:
            _STORE.save_in_connection(
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
    return _STORE.load_many(
        "assistant_runs",
        AssistantRun,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
    )


def save_assistant_evidence_bundle(bundle: AssistantEvidenceBundle) -> None:
    _STORE.save(
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
    return _STORE.load_many(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
        last_n=last_n,
    )


def save_assistant_memory_record(record: AssistantMemoryRecord) -> None:
    _STORE.save(
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

    return _STORE.load_many(
        "assistant_memory_records",
        AssistantMemoryRecord,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="created_at, id",
        last_n=last_n,
    )


def save_context_snapshot(snapshot: ContextSnapshot) -> None:
    _STORE.save(
        "context_snapshots",
        snapshot.id,
        snapshot.model_dump_json(),
        created_at=snapshot.created_at,
    )


def load_context_snapshot(snapshot_id: str) -> ContextSnapshot | None:
    return _STORE.load("context_snapshots", ContextSnapshot, snapshot_id)


def load_context_snapshots() -> list[ContextSnapshot]:
    return _STORE.load_many("context_snapshots", ContextSnapshot)


def save_evidence_card(card: EvidenceCard) -> None:
    _STORE.save("evidence_cards", card.id, card.model_dump_json())


def load_evidence_cards() -> list[EvidenceCard]:
    return _STORE.load_many("evidence_cards", EvidenceCard)


# ---------------------------------------------------------------------------
# Program storage
# ---------------------------------------------------------------------------


def save_program(program: Program) -> None:
    _STORE.save("programs", program.id, program.model_dump_json())


def load_program(program_id: str) -> Program | None:
    return _STORE.load("programs", Program, program_id)


def load_programs(status: str | None = None) -> list[Program]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _STORE.load_many(
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

        _STORE.save_in_connection(
            con,
            "programs",
            program.id,
            program.model_dump_json(),
        )
