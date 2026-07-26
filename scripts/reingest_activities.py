#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Rebuild running-activity tables from the FIT tree.

Needed after parser-field changes: wipes the running_activity_* tables and
the activities-tree fingerprint, then re-runs the ingest engine so every
file is re-parsed with the current parser (unchanged source signatures mean a
normal sync/startup ingest would otherwise skip already-seen files).

Usage:
    cd backend && uv run python ../scripts/reingest_activities.py
"""

import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.bootstrap.container import build_container
from app.core.config import get_app_config
from app.domains.garmin_sync.data_change import notify_data_changed
from app.domains.garmin_sync.infra.activity_ingest import ingest_running_activities
from app.infra.sqlite import connect

if __name__ == "__main__":
    activities_dir = get_app_config().activities_dir
    if not activities_dir.exists():
        print(f"Activities dir not found: {activities_dir} — refusing to wipe tables.")
        sys.exit(1)

    with connect() as con, con:
        for table in (
            "running_activity_sessions",
            "running_activity_laps",
            "running_activity_series",
            "running_activity_sources",
        ):
            con.execute(f"DELETE FROM {table}")
        con.execute("DELETE FROM ingest_meta WHERE key = 'activities_fingerprint'")

    print("Re-ingesting all running activity FIT files...")
    result = ingest_running_activities(activities_dir)
    notify_data_changed(build_container().garmin_sync)
    print(f"reingested: {result.sessions_ingested} sessions, {result.files_failed} failed")
