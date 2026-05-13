"""SQLite schema owned by the app profile slice.

Profile persistence still uses legacy helpers in ``app.infra.database``, but
the table definitions live with the core profile owner so global infrastructure
does not accumulate product schema details.
"""

from __future__ import annotations

import sqlite3

_JSON_COLS = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS user_profile ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS goals ({_JSON_COLS});
"""


def init_profile_schema(con: sqlite3.Connection) -> None:
    """Create profile-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
