"""Regression tests for Garmin download script helper policy."""

from __future__ import annotations

import json
import runpy
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "download_garmin.py"


def _script_namespace() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="__not_main__")


def test_activity_file_stem_uses_local_time_sport_and_sub_sport(tmp_path: Path):
    ns = _script_namespace()
    ns["_activity_file_stem_from_fit"].__globals__["_activity_kind_from_fit"] = (
        lambda _fit_path: "running_generic"
    )
    activity = {
        "activityId": 23398049297,
        "startTimeLocal": "2026-06-27 10:40:56",
    }
    fit_path = tmp_path / "download.fit"
    fit_path.write_bytes(b"fit")

    stem = ns["_activity_file_stem_from_fit"](
        tmp_path,
        "23398049297",
        activity,
        [fit_path],
    )

    assert stem == "104056_running_generic"


def test_activity_file_stem_appends_id_only_for_metadata_collision(tmp_path: Path):
    ns = _script_namespace()
    ns["_activity_file_stem_from_fit"].__globals__["_activity_kind_from_fit"] = (
        lambda _fit_path: "training_strength_training"
    )
    existing = tmp_path / "104056_training_strength_training.json"
    existing.write_text(json.dumps({"activityId": 111}), encoding="utf-8")
    activity = {
        "activityId": 23398049297,
        "startTimeLocal": "2026-06-27 10:40:56",
    }
    fit_path = tmp_path / "download.fit"
    fit_path.write_bytes(b"fit")

    stem = ns["_activity_file_stem_from_fit"](
        tmp_path,
        "23398049297",
        activity,
        [fit_path],
    )

    assert stem == "104056_training_strength_training_23398049297"


def test_existing_activity_stem_finds_renamed_activity_from_sidecar(tmp_path: Path):
    ns = _script_namespace()
    existing = tmp_path / "104056_running_generic.json"
    existing.write_text(json.dumps({"activityId": 23398049297}), encoding="utf-8")

    stem = ns["_existing_activity_stem"](tmp_path, "23398049297")

    assert stem == "104056_running_generic"


def test_health_data_date_range_uses_zip_and_extracted_day_entries(tmp_path: Path):
    ns = _script_namespace()
    (tmp_path / "2026-06-03.zip").write_bytes(b"zip")
    (tmp_path / "2026-06-01").mkdir()
    (tmp_path / "not-a-date.zip").write_bytes(b"ignored")

    start, end = ns["health_data_date_range"](tmp_path)

    assert (start, end) == (date(2026, 6, 1), date(2026, 6, 3))
