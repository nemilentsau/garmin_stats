"""One-time guarded reset for failed Coach and imported-training state."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

RESET_TABLES = (
    "coach_review_revisions",
    "coach_messages",
    "coach_threads",
    "coach_journal",
    "coach_brief_versions",
    "coach_reviews",
    "coach_jobs",
    "training_card_logs",
    "training_registry",
    "training_blocks",
    "training_exercise_library",
    "training_bundles",
)

_OBSOLETE_TABLES = ("activity_sync_coverage", "coach_reconciliation_state")
_APPLICATION_SCHEMA_MARKERS = frozenset(
    {"ingest_meta", "wellness_data", "training_bundles", "coach_jobs"}
)


@dataclass(frozen=True)
class ResetInspection:
    reset_table_counts: dict[str, int]
    coverage_table_present: bool
    coach_directory_present: bool
    coach_file_count: int
    preserved_fingerprint: str


@dataclass(frozen=True)
class ResetResult:
    executed: bool
    cleared_table_counts: dict[str, int]
    reset_table_counts: dict[str, int]
    coverage_table_present: bool
    preserved_fingerprint: str
    vacuum_completed: bool | None
    runtime_cleanup_completed: bool | None


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    return connection


def _validate_application_database(db_path: Path) -> None:
    """Fail closed unless ``db_path`` is an initialized Garmin Stats database."""
    if not db_path.exists():
        raise ValueError(f"database does not exist: {db_path}")
    if not db_path.is_file():
        raise ValueError(f"database path is not a regular file: {db_path}")
    try:
        connection = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise ValueError(f"database cannot be opened read-only: {db_path}") from error
    connection.row_factory = sqlite3.Row
    try:
        tables = _tables(connection)
    except sqlite3.DatabaseError as error:
        raise ValueError(f"database is not valid SQLite: {db_path}") from error
    finally:
        connection.close()
    missing = sorted(_APPLICATION_SCHEMA_MARKERS - tables)
    if missing:
        raise ValueError(
            f"not a Garmin Stats database; missing schema markers: {', '.join(missing)}"
        )


def _validated_paths(
    *,
    db_path: Path,
    wellness_dir: Path,
    activities_dir: Path,
    coach_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    db_path = db_path.resolve()
    wellness_dir = wellness_dir.resolve()
    activities_dir = activities_dir.resolve()
    coach_dir = coach_dir.resolve()
    _validate_application_database(db_path)
    expected_coach_dir = db_path.parent / "coach"
    if coach_dir != expected_coach_dir:
        raise ValueError(
            f"coach_dir must be the database sibling {expected_coach_dir}"
        )
    for label, preserved_path in (
        ("wellness_dir", wellness_dir),
        ("activities_dir", activities_dir),
    ):
        if (
            coach_dir == preserved_path
            or coach_dir in preserved_path.parents
            or preserved_path in coach_dir.parents
        ):
            raise ValueError(f"coach_dir must be disjoint from {label}")
    return db_path, wellness_dir, activities_dir, coach_dir


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _database_fingerprint(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    tables = _tables(connection)
    preserved_tables = sorted(
        table
        for table in tables
        if table not in RESET_TABLES
        and table not in _OBSOLETE_TABLES
        and not table.startswith("sqlite_")
    )
    for table in preserved_tables:
        digest.update(table.encode())
        columns = [
            str(row["name"])
            for row in connection.execute(f'PRAGMA table_info("{table}")')
        ]
        digest.update("\0".join(columns).encode())
        for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
            for value in row:
                data = (
                    bytes(value)
                    if isinstance(value, bytes)
                    else str(value).encode("utf-8")
                )
                digest.update(len(data).to_bytes(8, "big"))
                digest.update(data)
    return digest.hexdigest()


def _tree_fingerprint(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    digest.update(str(root.resolve()).encode())
    if not root.exists():
        digest.update(b"<missing>")
        return digest.hexdigest(), count
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        count += 1
        digest.update(path.relative_to(root).as_posix().encode())
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest(), count


def _preserved_fingerprint(
    connection: sqlite3.Connection, wellness_dir: Path, activities_dir: Path
) -> str:
    wellness_fingerprint, _ = _tree_fingerprint(wellness_dir)
    activity_fingerprint, _ = _tree_fingerprint(activities_dir)
    payload = ":".join(
        (
            _database_fingerprint(connection),
            wellness_fingerprint,
            activity_fingerprint,
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def inspect_failed_round(
    *,
    db_path: Path,
    wellness_dir: Path,
    activities_dir: Path,
    coach_dir: Path,
) -> ResetInspection:
    """Inventory reset-owned state and fingerprint every preserved data surface."""
    db_path, wellness_dir, activities_dir, coach_dir = _validated_paths(
        db_path=db_path,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    with _connect(db_path) as connection:
        tables = _tables(connection)
        counts = {
            table: _row_count(connection, table) if table in tables else 0
            for table in RESET_TABLES
        }
        preserved_fingerprint = _preserved_fingerprint(
            connection, wellness_dir, activities_dir
        )
    _, coach_file_count = _tree_fingerprint(coach_dir)
    return ResetInspection(
        reset_table_counts=counts,
        coverage_table_present="activity_sync_coverage" in tables,
        coach_directory_present=coach_dir.exists(),
        coach_file_count=coach_file_count,
        preserved_fingerprint=preserved_fingerprint,
    )


def reset_failed_round(
    *,
    db_path: Path,
    wellness_dir: Path,
    activities_dir: Path,
    coach_dir: Path,
    dry_run: bool = False,
) -> ResetResult:
    """Clear failed-round state transactionally while proving Garmin data is unchanged."""
    db_path, wellness_dir, activities_dir, coach_dir = _validated_paths(
        db_path=db_path,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    before = inspect_failed_round(
        db_path=db_path,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    if dry_run:
        return ResetResult(
            executed=False,
            cleared_table_counts=before.reset_table_counts,
            reset_table_counts=before.reset_table_counts,
            coverage_table_present=before.coverage_table_present,
            preserved_fingerprint=before.preserved_fingerprint,
            vacuum_completed=None,
            runtime_cleanup_completed=None,
        )

    quarantine: Path | None = None
    if coach_dir.exists():
        quarantine = coach_dir.with_name(
            f"{coach_dir.name}.reset-pending-{uuid4()}"
        )
        coach_dir.rename(quarantine)

    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(db_path)
        connection.execute("BEGIN EXCLUSIVE")
        preserved_before = _preserved_fingerprint(
            connection, wellness_dir, activities_dir
        )
        tables = _tables(connection)
        for table in RESET_TABLES:
            if table in tables:
                connection.execute(f'DELETE FROM "{table}"')
        for table in _OBSOLETE_TABLES:
            connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        preserved_after = _preserved_fingerprint(
            connection, wellness_dir, activities_dir
        )
        if preserved_after != preserved_before:
            raise RuntimeError("Preserved application data changed during reset")
        remaining = {
            table: _row_count(connection, table)
            for table in RESET_TABLES
            if table in tables
        }
        if any(remaining.values()):
            raise RuntimeError(f"Reset tables still contain rows: {remaining}")
        connection.commit()
    except BaseException:
        if connection is not None:
            connection.rollback()
        if quarantine is not None and quarantine.exists():
            quarantine.rename(coach_dir)
        raise
    finally:
        if connection is not None:
            connection.close()

    vacuum_completed = True
    try:
        with _connect(db_path) as vacuum_connection:
            vacuum_connection.execute("VACUUM")
    except sqlite3.DatabaseError:
        vacuum_completed = False

    runtime_cleanup_completed = True
    if quarantine is not None:
        try:
            shutil.rmtree(quarantine)
        except OSError:
            runtime_cleanup_completed = False

    after = inspect_failed_round(
        db_path=db_path,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    return ResetResult(
        executed=True,
        cleared_table_counts=before.reset_table_counts,
        reset_table_counts=after.reset_table_counts,
        coverage_table_present=after.coverage_table_present,
        preserved_fingerprint=after.preserved_fingerprint,
        vacuum_completed=vacuum_completed,
        runtime_cleanup_completed=runtime_cleanup_completed,
    )
