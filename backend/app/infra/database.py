"""
SQLite persistence layer for Garmin Stats.

Ingest adapters write Garmin health records into SQLite.
Read path helpers reconstruct persisted Pydantic models for API/domain adapters.
"""

import re
import sqlite3

from ..core.config import get_app_config
from ..core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    Goal,
    UserProfile,
)
from .jsonstore import JsonStore
from .sqlite import DB_PATH, connect

_APP_CONFIG = get_app_config()

DATA_DIR = _APP_CONFIG.data_dir

_ALIAS_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_VALID_TABLES = frozenset({
    "wellness_data", "sleep_data", "hrv_data",
    "skin_temp_data", "daily_metrics", "ingest_meta",
    "user_profile", "goals", "experiments", "experiment_exposures",
    "experiment_reports",
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
# Profile storage
# ---------------------------------------------------------------------------

def save_user_profile(profile: UserProfile) -> None:
    _STORE.save("user_profile", profile.id, profile.model_dump_json())


def load_user_profile(profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
    return _STORE.load("user_profile", UserProfile, profile_id)


def save_goal(goal: Goal) -> None:
    _STORE.save("goals", goal.id, goal.model_dump_json())


def load_goals() -> list[Goal]:
    return _STORE.load_many("goals", Goal)
