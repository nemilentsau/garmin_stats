"""SQLite schema for imported v3 training artifacts and capture logs.

Training owns five jsonstore tables: the imported bundle/block/registry/
library artifact wrappers (verbatim uploads plus lifecycle bookkeeping) and
the per-occurrence capture log. All five use the shared JSON-record column
shape (`id`, `data`, `created_at`, `updated_at`) with no bespoke columns or
indexes — lookups go through jsonstore's id/status/json-field predicates, and
read volume is small (one active block's worth of bundles/cards at a time),
so a dedicated index isn't worth the schema complexity yet.
"""

from __future__ import annotations

import sqlite3

from app.infra.jsonstore import JSON_RECORD_COLUMNS_SQL

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS training_bundles ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_blocks ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_registry ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_exercise_library ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_card_logs ({JSON_RECORD_COLUMNS_SQL});
"""


def init_training_schema(con: sqlite3.Connection) -> None:
    """Create training-owned tables using a caller-managed connection."""
    con.executescript(_SCHEMA)
