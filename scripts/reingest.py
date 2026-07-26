#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""One-time data re-ingestion script.

Re-parses all FIT files and stores results in SQLite.
Does not require the server to be running.

Usage:
    cd backend && uv run python ../scripts/reingest.py
"""

import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.bootstrap.schema import init_storage
from app.bootstrap.container import build_container
from app.core.config import get_app_config
from app.domains.garmin_sync.workflows import trigger_ingest

if __name__ == "__main__":
    data_dir = get_app_config().data_dir
    print(f"Data directory: {data_dir}")
    if not data_dir.exists():
        print(f"ERROR: data directory does not exist: {data_dir}")
        sys.exit(1)

    init_storage()
    print("Re-ingesting all FIT files...")
    result = trigger_ingest(build_container().garmin_sync)
    print(f"Done: {result.days_ingested} days ingested in {result.duration_ms} ms")
