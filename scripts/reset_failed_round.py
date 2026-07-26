#!/usr/bin/env python
"""Preview or execute the one-time failed Coach/training round reset."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.bootstrap.reset_failed_round import reset_failed_round  # noqa: E402
from app.core.config import get_app_config  # noqa: E402


def main() -> None:
    config = get_app_config()
    parser = argparse.ArgumentParser(
        description=(
            "Clear Coach, imported training, and experiment state while preserving "
            "Garmin SQLite rows and source files. Defaults to preview-only."
        )
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--db", type=Path, default=config.database_path)
    parser.add_argument("--wellness-dir", type=Path, default=config.data_dir)
    parser.add_argument("--activities-dir", type=Path, default=config.activities_dir)
    parser.add_argument(
        "--coach-dir",
        type=Path,
        default=config.database_path.parent / "coach",
    )
    args = parser.parse_args()
    result = reset_failed_round(
        db_path=args.db.resolve(),
        wellness_dir=args.wellness_dir.resolve(),
        activities_dir=args.activities_dir.resolve(),
        coach_dir=args.coach_dir.resolve(),
        dry_run=not args.execute,
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
