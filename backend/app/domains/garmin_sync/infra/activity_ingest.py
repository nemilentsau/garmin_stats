"""Idempotent running-activity ingest: activities tree → SQLite.

Owns the write path for ``running_activity_*`` tables and the activities-tree
fingerprint (``ingest_meta`` key ``activities_fingerprint``). Gate first, then
delta: an unchanged tree returns immediately with zero work; a changed tree
parses only files that have no session row yet (downloads are write-once, so
a ``source_file`` already on disk is never re-parsed — ``force`` bypasses the
fingerprint-equality skip but not this per-file dedup). Parsing itself belongs
to garmin_health's ``fit_parser``; this module only orchestrates and persists,
tolerating a per-file parse failure so one corrupt download never blocks the
rest of the batch. Invalidates the read cache only when rows were actually
written, never on a skip or an all-failed batch. Because the fingerprint is
written even when some files failed to parse, a file that fails once is not
retried until the activities tree fingerprint changes (i.e. any new download).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.domains.garmin_health.infra.fit_parser import (
    discover_running_activity_files,
    parse_running_activity,
)
from app.domains.garmin_sync.contracts import RunningActivityIngestResult
from app.domains.garmin_sync.infra.filesystem import compute_data_fingerprint
from app.infra import cache
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

log = logging.getLogger(__name__)

_FINGERPRINT_KEY = "activities_fingerprint"


def _get_meta(con: sqlite3.Connection, key: str) -> str | None:
    """Read a single ingest metadata value on a caller-managed connection."""
    row = con.execute("SELECT value FROM ingest_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def ingest_running_activities(
    activities_dir: Path, force: bool = False
) -> RunningActivityIngestResult:
    """Ingest new running FIT files; no-op when the tree fingerprint is unchanged.

    ``force=True`` bypasses only the fingerprint-equality skip (useful to force
    the fingerprint/meta row to be rewritten); it does not force re-parsing of
    files that already have a session row, since ``source_file`` is a stable,
    write-once identity for a downloaded activity.
    """
    current = compute_data_fingerprint(activities_dir)
    files = discover_running_activity_files(activities_dir)

    with connect() as con:
        if not force and _get_meta(con, _FINGERPRINT_KEY) == current:
            return RunningActivityIngestResult(skipped=True, files_seen=len(files))
        existing = {
            row["source_file"]
            for row in con.execute("SELECT source_file FROM running_activity_sessions")
        }

    new_files = [f for f in files if str(f.relative_to(activities_dir)) not in existing]

    ingested = 0
    failed = 0
    now = now_iso()
    with connect() as con, con:
        for fit_path in new_files:
            try:
                data = parse_running_activity(fit_path, activities_dir)
            except Exception as e:
                failed += 1
                log.warning("Activity ingest failed for %s: %s", fit_path, e)
                continue

            s = data.session
            con.execute(
                "INSERT OR REPLACE INTO running_activity_sessions "
                "(id, activity_id, session_date, start_time_local, sub_sport,"
                " source_file, data, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.id,
                    s.activity_id,
                    s.session_date,
                    s.start_time_local,
                    s.sub_sport,
                    s.source_file,
                    s.model_dump_json(),
                    now,
                    now,
                ),
            )
            con.execute("DELETE FROM running_activity_laps WHERE session_id = ?", (s.id,))
            for lap in data.laps:
                con.execute(
                    "INSERT INTO running_activity_laps (session_id, lap_index, data)"
                    " VALUES (?, ?, ?)",
                    (s.id, lap.lap_index, lap.model_dump_json()),
                )
            con.execute(
                "INSERT OR REPLACE INTO running_activity_series (session_id, data)"
                " VALUES (?, ?)",
                (s.id, data.series.model_dump_json()),
            )
            ingested += 1

        con.execute(
            "INSERT OR REPLACE INTO ingest_meta (key, value) VALUES (?, ?)",
            (_FINGERPRINT_KEY, current),
        )

    if ingested:
        cache.invalidate()

    return RunningActivityIngestResult(
        files_seen=len(files), sessions_ingested=ingested, files_failed=failed
    )
