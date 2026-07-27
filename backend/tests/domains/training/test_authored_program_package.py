"""Canonical checked-in authored program package contract."""

from __future__ import annotations

import json
from base64 import b64encode
from datetime import date
from zipfile import ZipFile

from app.domains.training.adapters import SqliteTrainingRepository
from app.domains.training.application.import_packages import (
    ImportPackageRequest,
    import_package,
)
from tests.domains.training._authored_program import (
    AUTHORED_ARTIFACT_NAMES,
    AUTHORED_PROGRAM_DIR,
    AUTHORED_PROGRAM_PACKAGE,
)


def test_authored_program_has_one_complete_zip_and_no_loose_json():
    assert AUTHORED_PROGRAM_PACKAGE.is_file()
    assert list(AUTHORED_PROGRAM_DIR.rglob("*.json")) == []
    assert list(AUTHORED_PROGRAM_DIR.rglob("*.zip")) == [AUTHORED_PROGRAM_PACKAGE]

    with ZipFile(AUTHORED_PROGRAM_PACKAGE) as package:
        assert set(package.namelist()) == AUTHORED_ARTIFACT_NAMES
        for name in AUTHORED_ARTIFACT_NAMES:
            assert isinstance(json.loads(package.read(name).decode("utf-8")), dict)


def test_authored_program_uses_human_facing_program_and_bundle_names():
    with ZipFile(AUTHORED_PROGRAM_PACKAGE) as package:
        block = json.loads(package.read("block1.json"))
        bundle_names = {
            name: json.loads(package.read(name))["name"]
            for name in ("running_v3.json", "strength_v3.json", "support_v3.json")
        }

    assert block["name"] == "Threshold Development"
    assert bundle_names == {
        "running_v3.json": "Running",
        "strength_v3.json": "Strength",
        "support_v3.json": "Support",
    }


def test_authored_program_zip_activates_through_production_importer():
    repo = SqliteTrainingRepository()

    result = import_package(
        repo,
        ImportPackageRequest(
            filename=AUTHORED_PROGRAM_PACKAGE.name,
            content_base64=b64encode(AUTHORED_PROGRAM_PACKAGE.read_bytes()).decode("ascii"),
            start_date=date(2026, 8, 3),
            warning_acks=[],
        ),
    )

    assert result.activated is True
