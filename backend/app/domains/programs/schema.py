"""SQLite schema for imported program specs and version history.

Programs owns persisted specs and immutable version rows.
"""

from __future__ import annotations

import sqlite3

from app.infra.jsonstore import JSON_RECORD_COLUMNS_SQL

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS programs ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS program_versions (
    program_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (program_id, version)
);
"""


def init_program_schema(con: sqlite3.Connection) -> None:
    """Create program-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
