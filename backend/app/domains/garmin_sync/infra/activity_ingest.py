"""Idempotent running-activity ingest: activities tree → SQLite.

Owns the write path for ``running_activity_*`` tables, per-source FIT+sidecar
signatures, and the activities-tree fingerprint (``ingest_meta`` key
``activities_fingerprint``). Gate first, then delta: an unchanged tree returns
immediately with zero work; a changed tree parses new or signature-changed
sources and atomically replaces their derived rows. Parsing itself belongs
to garmin_health's ``fit_parser``; this module only orchestrates and persists,
tolerating a per-file parse failure so one corrupt download never blocks the
rest of the batch. Invalidates the read cache only when rows were actually
written, never on a skip or an all-failed batch. A pass with any parse failure
leaves the fingerprint pending so an unchanged-tree startup retries that file.
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
from app.domains.garmin_sync.infra.filesystem import (
    compute_activity_source_fingerprint,
    compute_activity_tree_fingerprint,
)
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
    """Ingest new or changed running sources; no-op when the tree is unchanged.

    ``force=True`` bypasses only the fingerprint-equality skip (useful to force
    the fingerprint/meta row to be rewritten); unchanged source signatures are
    still not re-parsed.
    """
    files = discover_running_activity_files(activities_dir)
    current = compute_activity_tree_fingerprint(activities_dir, files)
    source_fingerprints = {
        str(fit_path.relative_to(activities_dir)): compute_activity_source_fingerprint(
            fit_path, activities_dir
        )
        for fit_path in files
    }

    with connect() as con:
        if not force and _get_meta(con, _FINGERPRINT_KEY) == current:
            return RunningActivityIngestResult(skipped=True, files_seen=len(files))
        existing_sessions = {
            row["source_file"]: row["id"]
            for row in con.execute("SELECT id, source_file FROM running_activity_sessions")
        }
        stored_fingerprints = {
            row["source_file"]: row["fingerprint"]
            for row in con.execute(
                "SELECT source_file, fingerprint FROM running_activity_sources"
            )
        }

    changed_files = [
        fit_path
        for fit_path in files
        if (
            (relative := str(fit_path.relative_to(activities_dir)))
            not in existing_sessions
            or stored_fingerprints.get(relative) != source_fingerprints[relative]
        )
    ]
    removed_sources = sorted(set(existing_sessions) - set(source_fingerprints))

    ingested = 0
    failed = 0
    now = now_iso()
    with connect() as con, con:
        for source_file in removed_sources:
            session_id = existing_sessions[source_file]
            con.execute(
                "DELETE FROM running_activity_laps WHERE session_id = ?", (session_id,)
            )
            con.execute(
                "DELETE FROM running_activity_series WHERE session_id = ?", (session_id,)
            )
            con.execute(
                "DELETE FROM running_activity_sessions WHERE source_file = ?",
                (source_file,),
            )
            con.execute(
                "DELETE FROM running_activity_sources WHERE source_file = ?",
                (source_file,),
            )
        for fit_path in changed_files:
            source_file = str(fit_path.relative_to(activities_dir))
            try:
                data = parse_running_activity(fit_path, activities_dir)
            except Exception as e:
                failed += 1
                log.warning("Activity ingest failed for %s: %s", fit_path, e)
                continue

            s = data.session
            old_session_id = existing_sessions.get(source_file)
            if old_session_id is not None:
                con.execute(
                    "DELETE FROM running_activity_laps WHERE session_id = ?",
                    (old_session_id,),
                )
                con.execute(
                    "DELETE FROM running_activity_series WHERE session_id = ?",
                    (old_session_id,),
                )
                con.execute(
                    "DELETE FROM running_activity_sessions WHERE source_file = ?",
                    (source_file,),
                )
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
            con.execute(
                "INSERT OR REPLACE INTO running_activity_sources "
                "(source_file, fingerprint, session_id) VALUES (?, ?, ?)",
                (source_file, source_fingerprints[source_file], s.id),
            )
            ingested += 1

        if failed == 0:
            con.execute(
                "INSERT OR REPLACE INTO ingest_meta (key, value) VALUES (?, ?)",
                (_FINGERPRINT_KEY, current),
            )

    if ingested or removed_sources:
        cache.invalidate()

    return RunningActivityIngestResult(
        files_seen=len(files), sessions_ingested=ingested, files_failed=failed
    )
