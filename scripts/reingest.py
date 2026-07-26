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
from app.core.config import get_app_config
from app.domains.garmin_sync.infra.filesystem import extract_existing_archives
from app.domains.garmin_sync.infra.sqlite_ingest import ingest_all

if __name__ == "__main__":
    data_dir = get_app_config().data_dir
    print(f"Data directory: {data_dir}")
    if not data_dir.exists():
        print(f"ERROR: data directory does not exist: {data_dir}")
        sys.exit(1)

    init_storage()
    extracted = extract_existing_archives(data_dir)
    if extracted:
        print(f"Extracted {extracted} pending archive(s)")
    print("Re-ingesting all FIT files...")
    result = ingest_all(data_dir)
    print(f"Done: {result.days_ingested} days ingested in {result.duration_ms} ms")
