"""SQLite schema for ingested Garmin day data.

Garmin sync owns writes to raw parsed day tables, the derived daily metric
table, and ingest metadata. Garmin analytics reads these tables through its own
repository, but creation stays with the ingest storage owner.
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
"""


def init_garmin_sync_schema(con: sqlite3.Connection) -> None:
    """Create Garmin ingest-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
