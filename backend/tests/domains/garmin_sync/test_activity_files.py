"""Tests for the garmin_activities filesystem layout and store adapter.

Covers payload-extraction equivalence classes (bare FIT, ZIP of FITs, junk),
stem naming from local start time plus decoded sport, sidecar-based
idempotence lookups, and stem-collision handling.
"""

from __future__ import annotations

import json
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from app.domains.garmin_sync.infra import activity_files
from app.domains.garmin_sync.infra.activity_files import (
    FilesystemActivityStore,
    existing_activity_stem,
    store_activity_payload,
)

METADATA = {"activityId": 23398049297, "startTimeLocal": "2026-06-27 10:40:56"}


@pytest.fixture(autouse=True)
def _fixed_fit_kind(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        activity_files, "_activity_kind_from_fit", lambda _path: "running_generic"
    )


def _zip_payload(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_store_bare_fit_payload_names_by_local_time_and_sport(tmp_path: Path):
    paths = store_activity_payload(tmp_path, "23398049297", METADATA, b"\x0eFITDATA")

    assert [p.name for p in paths] == ["104056_running_generic.fit"]
    sidecar = json.loads((tmp_path / "104056_running_generic.json").read_text())
    assert sidecar["activityId"] == 23398049297


def test_store_zip_payload_extracts_only_fit_members(tmp_path: Path):
    payload = _zip_payload({"a.fit": b"one", "b.fit": b"two", "notes.txt": b"skip"})

    paths = store_activity_payload(tmp_path, "1", METADATA, payload)

    assert [p.name for p in paths] == [
        "104056_running_generic.fit",
        "104056_running_generic_part2.fit",
    ]


def test_store_zip_without_fit_members_raises_and_leaves_no_files(tmp_path: Path):
    payload = _zip_payload({"readme.txt": b"no fits"})
    before = set(tmp_path.iterdir())

    with pytest.raises(ValueError):
        store_activity_payload(tmp_path, "1", METADATA, payload)
    assert set(tmp_path.iterdir()) == before


def test_store_corrupt_zip_payload_raises_value_error(tmp_path: Path):
    with pytest.raises(ValueError):
        store_activity_payload(tmp_path, "1", METADATA, b"PK\x03\x04garbage")


def test_stem_appends_activity_id_only_on_sidecar_collision(tmp_path: Path):
    (tmp_path / "104056_running_generic.json").write_text(json.dumps({"activityId": 111}))

    paths = store_activity_payload(tmp_path, "23398049297", METADATA, b"\x0eFIT")

    assert paths[0].name == "104056_running_generic_23398049297.fit"


def test_stem_falls_back_when_metadata_lacks_start_time(tmp_path: Path):
    paths = store_activity_payload(tmp_path, "5", {"activityId": 5}, b"\x0eFIT")

    assert paths[0].name == "unknown-time_running_generic.fit"


def test_existing_activity_stem_matches_sidecar_activity_id(tmp_path: Path):
    (tmp_path / "104056_running_generic.json").write_text(
        json.dumps({"activityId": 23398049297})
    )

    assert existing_activity_stem(tmp_path, "23398049297") == "104056_running_generic"
    assert existing_activity_stem(tmp_path, "999") is None


def test_store_adapter_round_trips_day_directories(tmp_path: Path):
    store = FilesystemActivityStore()
    day = date(2026, 6, 27)

    assert store.has_activity(tmp_path, day, "23398049297") is False
    store.store_activity(tmp_path, day, "23398049297", METADATA, b"\x0eFIT")

    assert store.has_activity(tmp_path, day, "23398049297") is True
    assert (tmp_path / "2026-06-27" / "104056_running_generic.fit").exists()
