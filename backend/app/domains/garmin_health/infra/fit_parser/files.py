"""Filesystem discovery helpers for extracted Garmin FIT day directories.

This module owns the data-root scan policy used by ingestion and parser entry
points.  It deliberately stays independent of FIT decoding so callers can group
available files without paying decode costs or importing parser internals.
"""

from collections import defaultdict
from datetime import date as date_cls
from pathlib import Path


def _is_canonical_day_dir_name(name: str) -> bool:
    """Return True only for exact YYYY-MM-DD day directory names."""
    if len(name) != 10:
        return False
    try:
        return date_cls.fromisoformat(name).isoformat() == name
    except ValueError:
        return False


def _classify_fit_file_type(fit_file: Path) -> str:
    """Derive the Garmin file-type tag from a `{timestamp}_{TYPE}.fit` filename."""
    name_parts = fit_file.stem.split("_")
    return "_".join(name_parts[1:]) if len(name_parts) >= 2 else "UNKNOWN"


def get_files_by_day(data_dir: Path) -> dict[str, dict[str, list[Path]]]:
    """Group extracted FIT files by canonical day directory and Garmin file type."""
    files_by_day: dict[str, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))

    for fit_file in data_dir.rglob("*.fit"):
        rel_parts = fit_file.relative_to(data_dir).parts
        if not rel_parts:
            continue
        date_dir = rel_parts[0]
        if not _is_canonical_day_dir_name(date_dir):
            continue
        files_by_day[date_dir][_classify_fit_file_type(fit_file)].append(fit_file)

    return {k: dict(v) for k, v in sorted(files_by_day.items())}
