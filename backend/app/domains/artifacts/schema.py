"""SQLite schema for assistant-authored artifact staging.

Artifacts owns staged assistant outputs before they are validated and delegated
to live domain repositories. The table is initialized here so artifact storage
can evolve without changing global database bootstrap internals.
"""

from __future__ import annotations

import sqlite3

_JSON_COLS = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS assistant_artifacts ({_JSON_COLS});
"""


def init_artifact_schema(con: sqlite3.Connection) -> None:
    """Create artifact-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
