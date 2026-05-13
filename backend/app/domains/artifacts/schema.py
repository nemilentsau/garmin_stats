"""SQLite schema for assistant-authored artifact staging.

Artifacts owns staged assistant outputs before they are validated and delegated
to live domain repositories.
"""

from __future__ import annotations

import sqlite3

from app.infra.jsonstore import JSON_RECORD_COLUMNS_SQL

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS assistant_artifacts ({JSON_RECORD_COLUMNS_SQL});
"""


def init_artifact_schema(con: sqlite3.Connection) -> None:
    """Create artifact-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
