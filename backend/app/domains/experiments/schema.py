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
"""

_AUTO_EXPOSURE_ID_PATTERN = "exposure:auto:%"
_UNIQUE_EXPOSURE_INDEX = "uq_experiment_exposures_experiment_date"


def _migrate_manual_exposures(con: sqlite3.Connection) -> None:
    """Purge derived rows and enforce one manual exposure per experiment-day."""
    con.execute(
        """
        WITH affected_experiments AS (
            SELECT experiment_id
            FROM experiment_exposures
            WHERE id LIKE ?
            UNION
            SELECT experiment_id
            FROM experiment_exposures
            GROUP BY experiment_id, entry_date
            HAVING COUNT(*) > 1
        )
        DELETE FROM experiment_analyses
        WHERE experiment_id IN (SELECT experiment_id FROM affected_experiments)
        """,
        (_AUTO_EXPOSURE_ID_PATTERN,),
    )
    con.execute(
        "DELETE FROM experiment_exposures WHERE id LIKE ?",
        (_AUTO_EXPOSURE_ID_PATTERN,),
    )
    con.execute(
        """
        DELETE FROM experiment_exposures AS candidate
        WHERE EXISTS (
            SELECT 1
            FROM experiment_exposures AS newer
            WHERE newer.experiment_id = candidate.experiment_id
              AND newer.entry_date = candidate.entry_date
              AND (
                  newer.updated_at > candidate.updated_at
                  OR (
                      newer.updated_at = candidate.updated_at
                      AND newer.created_at > candidate.created_at
                  )
                  OR (
                      newer.updated_at = candidate.updated_at
                      AND newer.created_at = candidate.created_at
                      AND newer.id > candidate.id
                  )
              )
        )
        """
    )
    con.execute("DROP INDEX IF EXISTS idx_experiment_exposures_experiment_date")
    con.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {_UNIQUE_EXPOSURE_INDEX} "
        "ON experiment_exposures (experiment_id, entry_date)"
    )


def init_experiment_schema(con: sqlite3.Connection) -> None:
    """Create experiment-owned tables and indexes using a caller-managed connection."""
    con.executescript(_SCHEMA)
    _migrate_manual_exposures(con)
