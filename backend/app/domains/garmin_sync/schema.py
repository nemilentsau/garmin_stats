"""SQLite schema for ingested Garmin day and running-activity data.

Garmin sync owns writes to raw parsed day tables, the derived daily metric
table, ingest metadata, and the session-grain ``running_activity_*`` tables.
Day tables are one-row-per-date (``_DAY_COLS``); activities are many-per-day
and keyed by session ``id`` instead, with ``source_file`` uniquely indexed so
delta ingest can detect "already have this one" by path alone. Garmin
analytics reads these tables through its own repository, but creation stays
with the ingest storage owner.
"""

from __future__ import annotations

import sqlite3

_DAY_COLS = "date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS wellness_data ({_DAY_COLS});
CREATE TABLE IF NOT EXISTS sleep_data ({_DAY_COLS});
CREATE TABLE IF NOT EXISTS hrv_data ({_DAY_COLS});
CREATE TABLE IF NOT EXISTS skin_temp_data ({_DAY_COLS});
CREATE TABLE IF NOT EXISTS daily_metrics ({_DAY_COLS});
CREATE TABLE IF NOT EXISTS ingest_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS running_activity_sessions (
    id TEXT PRIMARY KEY,
    activity_id TEXT,
    session_date TEXT NOT NULL,
    start_time_local TEXT NOT NULL,
    sub_sport TEXT,
    source_file TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_running_activity_sessions_date_start
    ON running_activity_sessions (session_date, start_time_local);
CREATE INDEX IF NOT EXISTS idx_running_activity_sessions_activity_id
    ON running_activity_sessions (activity_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_running_activity_sessions_source_file
    ON running_activity_sessions (source_file);
CREATE TABLE IF NOT EXISTS running_activity_laps (
    session_id TEXT NOT NULL,
    lap_index INTEGER NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (session_id, lap_index)
);
CREATE TABLE IF NOT EXISTS running_activity_series (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


def init_garmin_sync_schema(con: sqlite3.Connection) -> None:
    """Create Garmin ingest-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
