#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Rebuild running-activity tables from the FIT tree.

Needed after parser-field changes: wipes the running_activity_* tables and
the activities-tree fingerprint, then re-runs the ingest engine so every
file is re-parsed with the current parser (source_file dedup means a normal
sync/startup ingest would otherwise skip already-seen files).

Usage:
    cd backend && uv run python ../scripts/reingest_activities.py
"""

import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import get_app_config
from app.domains.garmin_sync.infra.activity_ingest import ingest_running_activities
from app.infra.sqlite import connect

if __name__ == "__main__":
    with connect() as con, con:
        for table in (
            "running_activity_sessions",
            "running_activity_laps",
            "running_activity_series",
        ):
            con.execute(f"DELETE FROM {table}")
        con.execute("DELETE FROM ingest_meta WHERE key = 'activities_fingerprint'")

    print("Re-ingesting all running activity FIT files...")
    result = ingest_running_activities(get_app_config().activities_dir)
    print(f"reingested: {result.sessions_ingested} sessions, {result.files_failed} failed")
