"""Storage schema composition for the application process.

SQLite primitives live in ``app.infra.sqlite``; per-table ownership lives beside
the storage adapters that read and write those tables. This module ensures the
database file exists, enables WAL, and invokes each slice-owned schema
initializer under one connection.
"""

import sqlite3

from app.core.profile.schema import init_profile_schema
from app.domains.artifacts.schema import init_artifact_schema
from app.domains.coach.schema import init_coach_schema
from app.domains.experiments.schema import init_experiment_schema
from app.domains.garmin_sync.schema import init_garmin_sync_schema
from app.domains.journal.schema import init_journal_schema
from app.domains.programs.schema import init_program_schema
from app.domains.routines.schema import init_routine_schema
from app.domains.training.schema import init_training_schema
from app.infra import sqlite

_RETIRED_ASSISTANT_TABLES = (
    "assistant_threads",
    "assistant_messages",
    "assistant_runs",
    "assistant_evidence_bundles",
    "assistant_memory_records",
    "context_snapshots",
    "evidence_cards",
    "plans",
    "plan_items",
)


def _drop_retired_assistant_tables(connection: sqlite3.Connection) -> None:
    """Remove the backed-up chat implementation without touching artifact ingress."""
    for table in _RETIRED_ASSISTANT_TABLES:
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')


def init_storage() -> None:
    """Ensure the SQLite file exists, enable WAL, and create every owned schema."""
    sqlite.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite.connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        init_garmin_sync_schema(con)
        init_profile_schema(con)
        init_artifact_schema(con)
        init_coach_schema(con)
        init_routine_schema(con)
        init_journal_schema(con)
        init_experiment_schema(con)
        init_program_schema(con)
        init_training_schema(con)
        _drop_retired_assistant_tables(con)
        con.commit()
