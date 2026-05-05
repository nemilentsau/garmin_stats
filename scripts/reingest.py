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

from app.infra.database import DATA_DIR, init_db, ingest_all

if __name__ == "__main__":
    print(f"Data directory: {DATA_DIR}")
    if not DATA_DIR.exists():
        print(f"ERROR: data directory does not exist: {DATA_DIR}")
        sys.exit(1)

    init_db()
    print("Re-ingesting all FIT files...")
    result = ingest_all(DATA_DIR)
    print(f"Done: {result.days_ingested} days ingested in {result.duration_ms} ms")
