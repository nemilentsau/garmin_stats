"""Regression tests for Garmin download script CLI policy."""

from __future__ import annotations

import runpy
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "download_garmin.py"


def _script_namespace() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="__not_main__")


def test_health_data_date_range_uses_zip_and_extracted_day_entries(tmp_path: Path):
    ns = _script_namespace()
    (tmp_path / "2026-06-03.zip").write_bytes(b"zip")
    (tmp_path / "2026-06-01").mkdir()
    (tmp_path / "not-a-date.zip").write_bytes(b"ignored")

    start, end = ns["health_data_date_range"](tmp_path)

    assert (start, end) == (date(2026, 6, 1), date(2026, 6, 3))
