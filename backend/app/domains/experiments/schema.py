"""SQLite schema for experiment definitions, exposures, and analyses.

The experiments domain owns spec persistence, day-grain exposure rows, and
cached N=1 analysis snapshots. The schema stays beside the adapter so
analysis-cache storage can evolve with experiment lifecycle policy.
"""

from __future__ import annotations

import sqlite3

from app.infra.jsonstore import JSON_RECORD_COLUMNS_SQL

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS experiments ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS experiment_exposures (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_analyses (
    experiment_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiment_exposures_experiment_date
    ON experiment_exposures (experiment_id, entry_date);
"""


def init_experiment_schema(con: sqlite3.Connection) -> None:
    """Create experiment-owned tables and indexes using a caller-managed connection."""
    con.executescript(_SCHEMA)
