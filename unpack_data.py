#!/usr/bin/env python3
"""
Unpack Garmin data zip files into per-day directories.

Each YYYY-MM-DD.zip in the data directory is extracted into a
data/YYYY-MM-DD/ folder. Already-extracted days are skipped.

Usage:
    python unpack_data.py [--data-dir DATA_DIR] [--force]
"""

import argparse
import zipfile
from pathlib import Path


def unpack_zips(data_dir: Path, force: bool = False) -> None:
    zip_files = sorted(data_dir.glob("*.zip"))
    if not zip_files:
        print("No zip files found.")
        return

    print(f"Found {len(zip_files)} zip file(s) in {data_dir}")

    extracted = 0
    skipped = 0
    for zf in zip_files:
        day_name = zf.stem  # e.g. "2026-01-01"
        dest = data_dir / day_name

        if dest.exists() and not force:
            skipped += 1
            continue

        dest.mkdir(exist_ok=True)
        with zipfile.ZipFile(zf) as z:
            z.extractall(dest)
        extracted += 1
        print(f"  Extracted {zf.name} -> {day_name}/")

    print(f"\nDone: {extracted} extracted, {skipped} skipped (already exist).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unpack Garmin data zip files")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
        help="Directory containing zip files (default: data/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if the destination directory already exists",
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"Error: directory '{args.data_dir}' not found")
        return 1

    unpack_zips(args.data_dir, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
