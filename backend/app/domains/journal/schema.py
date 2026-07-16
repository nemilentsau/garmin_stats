"""SQLite schema for journal check-ins and notes.

Journal owns subjective daily context used by routes, Coach evidence, and
experiment confounder analysis. Date indexes live with the schema because most
read paths are day-window based.
"""

from __future__ import annotations

import sqlite3

_SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_daily_checkins_entry_date
    ON daily_checkins (entry_date);
CREATE INDEX IF NOT EXISTS idx_notes_entry_date
    ON notes (entry_date);
"""


def init_journal_schema(con: sqlite3.Connection) -> None:
    """Create journal-owned tables and indexes using a caller-managed connection."""
    con.executescript(_SCHEMA)
