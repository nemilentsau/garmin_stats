"""Storage schema composition for the application process.

SQLite primitives live in ``app.infra.sqlite``; per-table ownership lives beside
the storage adapters that read and write those tables. This module ensures the
database file exists, enables WAL, and invokes each slice-owned schema
initializer under one connection.
"""

import sqlite3
from datetime import UTC, datetime

from app.bootstrap.training_coach_identity import (
    legacy_coach_occurrence_identity_migration_pending,
    migrate_legacy_coach_occurrence_identity,
)
from app.core.profile.schema import init_profile_schema
from app.domains.coach.schema import init_coach_schema
from app.domains.experiments.schema import init_experiment_schema
from app.domains.garmin_sync.schema import init_garmin_sync_schema
from app.domains.journal.schema import init_journal_schema
from app.domains.training.schema import (
    init_training_schema,
    program_instance_identity_migration_pending,
)
from app.infra import sqlite

_RETIRED_TABLES = (
    "assistant_artifacts",
    "card_templates",
    "routines",
    "routine_entries",
    "routine_schedules",
    "routine_assignments",
    "card_logs",
    "card_overrides",
    "assistant_threads",
    "assistant_messages",
    "assistant_runs",
    "assistant_evidence_bundles",
    "assistant_memory_records",
    "context_snapshots",
    "evidence_cards",
    "plans",
    "plan_items",
    "program_versions",
    "programs",
)


def _drop_retired_tables(connection: sqlite3.Connection) -> None:
    """Remove tables whose product surfaces and storage owners have been retired."""
    for table in _RETIRED_TABLES:
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')


def _destructive_migration_pending(connection: sqlite3.Connection) -> bool:
    """True when startup migrations would irreversibly rewrite or delete user data.

    Does not cover the coach `json_remove` blob rewrite in ``init_coach_schema``:
    that migration only strips redundant derived data and is judged non-destructive.
    """
    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    for table in _RETIRED_TABLES:
        if table in tables:
            count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if count:
                return True
    if "experiment_exposures" in tables:
        count = connection.execute(
            "SELECT COUNT(*) FROM experiment_exposures WHERE id LIKE 'exposure:auto:%'"
        ).fetchone()[0]
        if count:
            return True
        duplicate = connection.execute(
            "SELECT 1 FROM experiment_exposures "
            "GROUP BY experiment_id, entry_date HAVING COUNT(*) > 1 LIMIT 1"
        ).fetchone()
        if duplicate:
            return True
    training_identity_pending = program_instance_identity_migration_pending(connection)
    if training_identity_pending:
        return True
    return legacy_coach_occurrence_identity_migration_pending(connection)


def _backup_database() -> None:
    """Copy the DB file aside before a destructive migration; keeps history recoverable."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = sqlite.DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"pre-migration-{stamp}.db"
    with sqlite.connect() as source:
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
        finally:
            target.close()


def init_storage() -> None:
    """Ensure the SQLite file exists, enable WAL, and create every owned schema."""
    sqlite.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if sqlite.DB_PATH.exists():
        with sqlite.connect() as con:
            if _destructive_migration_pending(con):
                _backup_database()
    with sqlite.connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        init_garmin_sync_schema(con)
        init_profile_schema(con)
        init_coach_schema(con)
        init_journal_schema(con)
        init_experiment_schema(con)
        init_training_schema(con)
        migrate_legacy_coach_occurrence_identity(con)
        _drop_retired_tables(con)
        con.commit()
