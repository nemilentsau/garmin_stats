"""Storage schema composition for the application process.

SQLite primitives live in ``app.infra.sqlite``; per-table ownership lives beside
the storage adapters that read and write those tables. This module is the
bootstrap composition point that ensures the database file exists, configures
WAL, and creates every owned schema in a single connection so infra never has
to know product table names.
"""

from app.core.profile.schema import init_profile_schema
from app.domains.artifacts.schema import init_artifact_schema
from app.domains.assistant.schema import init_assistant_schema
from app.domains.experiments.schema import init_experiment_schema
from app.domains.garmin_sync.schema import init_garmin_sync_schema
from app.domains.journal.schema import init_journal_schema
from app.domains.programs.schema import init_program_schema
from app.domains.routines.schema import init_routine_schema
from app.infra import sqlite


def init_storage() -> None:
    """Ensure the SQLite file exists, enable WAL, and create every owned schema."""
    sqlite.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite.connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        init_garmin_sync_schema(con)
        init_profile_schema(con)
        init_assistant_schema(con)
        init_artifact_schema(con)
        init_routine_schema(con)
        init_journal_schema(con)
        init_experiment_schema(con)
        init_program_schema(con)
        con.commit()
