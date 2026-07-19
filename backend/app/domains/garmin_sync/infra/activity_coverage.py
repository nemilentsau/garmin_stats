"""SQLite proof that Garmin activity listing completed for a local date."""

from __future__ import annotations

from datetime import date

from app.infra.sqlite import connect
from app.utils.timeutil import now_iso


class SqliteActivitySyncCoverage:
    """Persist complete per-date activity sweeps for downstream absence checks."""

    def mark_covered(self, day: date) -> None:
        with connect() as connection, connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO activity_sync_coverage (date, covered_at)
                VALUES (?, ?)
                """,
                (day.isoformat(), now_iso()),
            )

    def mark_incomplete(self, day: date) -> None:
        with connect() as connection, connection:
            connection.execute(
                "DELETE FROM activity_sync_coverage WHERE date = ?",
                (day.isoformat(),),
            )

    def is_covered(self, day_iso: str) -> bool:
        with connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM activity_sync_coverage WHERE date = ?",
                (day_iso,),
            ).fetchone()
        return row is not None
