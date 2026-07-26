"""Guardrails for clearing failed Coach/training state without touching Garmin data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.bootstrap.reset_failed_round import inspect_failed_round, reset_failed_round
from app.infra import sqlite


def _insert_json_row(table: str, row_id: str) -> None:
    with sqlite.connect() as connection, connection:
        connection.execute(
            f"""
            INSERT INTO {table} (id, data, created_at, updated_at)
            VALUES (?, '{{}}', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')
            """,
            (row_id,),
        )


def _seed_failed_round(db_path: Path) -> None:
    _insert_json_row("training_bundles", "bundle-1")
    with sqlite.connect() as connection, connection:
        connection.execute(
            """
            INSERT INTO coach_jobs
                (id, kind, dedupe_key, priority, status, available_at,
                 created_at, updated_at, data)
            VALUES (
                'job-1', 'review_run', 'review:run:run-1', 10, 'complete',
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z',
                '2026-07-01T00:00:00Z', '{}'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE activity_sync_coverage (
                sync_id TEXT PRIMARY KEY,
                covered_through TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO activity_sync_coverage VALUES ('sync-1', '2026-07-01')"
        )
        connection.execute(
            """
            INSERT INTO wellness_data (date, data, updated_at)
            VALUES ('2026-07-01', '{"resting_hr": 48}', '2026-07-01T00:00:00Z')
            """
        )
        connection.execute(
            """
            INSERT INTO running_activity_sessions
                (id, session_date, start_time_local, source_file, data,
                 created_at, updated_at)
            VALUES (
                'run-1', '2026-07-01', '08:00:00', 'run.fit', '{"distance": 1000}',
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'
            )
            """
        )


def _seed_preserved_goal_and_experiment_state() -> None:
    _insert_json_row("experiments", "experiment-1")
    with sqlite.connect() as connection, connection:
        connection.executescript(
            """
            CREATE TABLE goals (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE experiment_reports (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                report_date TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO goals VALUES (
                'goal-1', '{"target": "stay healthy"}',
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'
            );
            INSERT INTO experiment_exposures VALUES (
                'exposure-1', 'experiment-1', '2026-07-01', '{}',
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'
            );
            INSERT INTO experiment_analyses VALUES (
                'experiment-1', '{}',
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'
            );
            INSERT INTO experiment_reports VALUES (
                'report-1', 'experiment-1', '2026-07-01', '{}',
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z'
            );
            """
        )


def _table_counts(*tables: str) -> dict[str, int]:
    with sqlite.connect() as connection:
        return {
            table: int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
            for table in tables
        }


def _seed_garmin_files(wellness_dir: Path, activities_dir: Path) -> None:
    wellness_dir.mkdir(parents=True)
    activities_dir.mkdir(parents=True)
    (wellness_dir / "daily.fit").write_bytes(b"wellness")
    (activities_dir / "run.fit").write_bytes(b"activity")


def test_reset_clears_failed_round_and_preserves_garmin_rows_and_files(
    tmp_db: Path, tmp_path: Path
):
    _seed_failed_round(tmp_db)
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    coach_dir = tmp_path / "coach"
    _seed_garmin_files(wellness_dir, activities_dir)
    coach_dir.mkdir()
    (coach_dir / "workspace.md").write_text("failed round")
    before = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )

    result = reset_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    after = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )

    assert result.executed is True
    assert result.vacuum_completed is True
    assert result.runtime_cleanup_completed is True
    assert result.preserved_fingerprint == before.preserved_fingerprint
    assert after.preserved_fingerprint == before.preserved_fingerprint
    assert all(count == 0 for count in after.reset_table_counts.values())
    assert after.coverage_table_present is False
    assert coach_dir.exists() is False


def test_reset_preserves_goals_and_every_experiment_table(
    tmp_db: Path, tmp_path: Path
):
    _seed_failed_round(tmp_db)
    _seed_preserved_goal_and_experiment_state()
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    coach_dir = tmp_path / "coach"
    _seed_garmin_files(wellness_dir, activities_dir)
    preserved_tables = (
        "goals",
        "experiments",
        "experiment_exposures",
        "experiment_analyses",
        "experiment_reports",
    )
    counts_before = _table_counts(*preserved_tables)
    fingerprint_before = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    ).preserved_fingerprint

    result = reset_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )

    assert _table_counts(*preserved_tables) == counts_before
    assert result.preserved_fingerprint == fingerprint_before


def test_preservation_fingerprint_includes_goals_and_every_experiment_table(
    tmp_db: Path, tmp_path: Path
):
    _seed_preserved_goal_and_experiment_state()
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    coach_dir = tmp_path / "coach"
    _seed_garmin_files(wellness_dir, activities_dir)
    def inspection() -> str:
        return inspect_failed_round(
            db_path=tmp_db,
            wellness_dir=wellness_dir,
            activities_dir=activities_dir,
            coach_dir=coach_dir,
        ).preserved_fingerprint
    prior = inspection()
    mutations = (
        ("goals", "id", "goal-1"),
        ("experiments", "id", "experiment-1"),
        ("experiment_exposures", "id", "exposure-1"),
        ("experiment_analyses", "experiment_id", "experiment-1"),
        ("experiment_reports", "id", "report-1"),
    )

    for table, key_column, row_id in mutations:
        with sqlite.connect() as connection, connection:
            connection.execute(
                f'UPDATE "{table}" SET data = ? WHERE "{key_column}" = ?',
                (f'{{"changed": "{table}"}}', row_id),
            )
        current = inspection()
        assert current != prior, f"{table} is missing from the preservation fingerprint"
        prior = current


def test_preservation_fingerprint_covers_future_non_reset_tables(
    tmp_db: Path, tmp_path: Path
):
    with sqlite.connect() as connection, connection:
        connection.execute(
            "CREATE TABLE future_user_state (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO future_user_state VALUES ('state-1', '{}')")
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    coach_dir = tmp_path / "coach"
    _seed_garmin_files(wellness_dir, activities_dir)

    before = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    ).preserved_fingerprint
    with sqlite.connect() as connection, connection:
        connection.execute(
            "UPDATE future_user_state SET data = '{\"changed\": true}'"
        )
    after = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    ).preserved_fingerprint

    assert after != before


def test_reset_dry_run_and_second_execution_are_noops(tmp_db: Path, tmp_path: Path):
    _seed_failed_round(tmp_db)
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    coach_dir = tmp_path / "coach"
    _seed_garmin_files(wellness_dir, activities_dir)
    coach_dir.mkdir()
    before = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )

    dry_run = reset_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
        dry_run=True,
    )
    unchanged = inspect_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    first = reset_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )
    second = reset_failed_round(
        db_path=tmp_db,
        wellness_dir=wellness_dir,
        activities_dir=activities_dir,
        coach_dir=coach_dir,
    )

    assert dry_run.executed is False
    assert unchanged == before
    assert first.executed is True
    assert second.executed is True
    assert all(count == 0 for count in second.reset_table_counts.values())


def test_reset_rolls_back_all_database_deletes_on_failure(
    tmp_db: Path, tmp_path: Path
):
    _seed_failed_round(tmp_db)
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    coach_dir = tmp_path / "coach"
    _seed_garmin_files(wellness_dir, activities_dir)
    coach_dir.mkdir()
    with sqlite.connect() as connection, connection:
        connection.execute(
            """
            CREATE TRIGGER block_coach_reset
            BEFORE DELETE ON coach_jobs
            BEGIN
                SELECT RAISE(ABORT, 'blocked reset');
            END
            """
        )

    with pytest.raises(sqlite3.DatabaseError, match="blocked reset"):
        reset_failed_round(
            db_path=tmp_db,
            wellness_dir=wellness_dir,
            activities_dir=activities_dir,
            coach_dir=coach_dir,
        )

    with sqlite.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM training_bundles"
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM coach_jobs").fetchone()[0] == 1
    assert coach_dir.exists()


def test_reset_rejects_coach_path_that_could_delete_garmin_files(
    tmp_db: Path, tmp_path: Path
):
    _seed_failed_round(tmp_db)
    wellness_dir = tmp_path / "wellness"
    activities_dir = tmp_path / "activities"
    _seed_garmin_files(wellness_dir, activities_dir)

    with pytest.raises(ValueError, match="database sibling"):
        reset_failed_round(
            db_path=tmp_db,
            wellness_dir=wellness_dir,
            activities_dir=activities_dir,
            coach_dir=wellness_dir,
        )

    assert (wellness_dir / "daily.fit").read_bytes() == b"wellness"
    with sqlite.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM coach_jobs").fetchone()[0] == 1
