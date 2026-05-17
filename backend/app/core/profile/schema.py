"""SQLite schema owned by the app profile slice.

Profile is core app configuration rather than a product domain, so its table
definitions live beside the profile adapter.
"""

from __future__ import annotations

import sqlite3

from app.infra.jsonstore import JSON_RECORD_COLUMNS_SQL

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS user_profile ({JSON_RECORD_COLUMNS_SQL});
"""


def init_profile_schema(con: sqlite3.Connection) -> None:
    """Create profile-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
