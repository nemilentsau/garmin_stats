"""One-file training package decoding and atomic import tests."""

from __future__ import annotations

import json
from base64 import b64encode
from datetime import date
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pydantic import ValidationError

from app.domains.training.adapters import SqliteTrainingRepository
from app.domains.training.application import import_packages
from app.domains.training.application.import_packages import (
    ImportPackageRequest,
    import_package,
)
from tests._architecture import REPO_ROOT

CALIBRATION_FIXTURE = (
    REPO_ROOT / "backend" / "tests" / "fixtures" / "training" / "v3-calibration"
)
_ARTIFACT_FILENAMES = (
    "block0.json",
    "running_v3.json",
    "strength_v3.json",
    "support_v3.json",
    "registry.json",
    "exercise_library.json",
)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _zip_base64(entries: dict[str, bytes]) -> str:
    return b64encode(_zip_bytes(entries)).decode("ascii")


def _request(content_base64: str, *, filename: str = "training.zip") -> ImportPackageRequest:
    return ImportPackageRequest(
        filename=filename,
        content_base64=content_base64,
        start_date=date(2026, 8, 3),
        warning_acks=[],
    )


def _calibration_entries(*, root: str = "training-package") -> dict[str, bytes]:
    return {
        f"{root}/{name}": (CALIBRATION_FIXTURE / name).read_bytes()
        for name in _ARTIFACT_FILENAMES
    }


def test_package_import_activates_nested_json_artifacts_and_ignores_other_files():
    entries = {
        **_calibration_entries(),
        "training-package/README.md": b"Authored package notes",
        "__MACOSX/._block0.json": b"Finder metadata",
        "training-package/.DS_Store": b"Finder metadata",
    }
    repo = SqliteTrainingRepository()

    result = import_package(
        repo,
        ImportPackageRequest(
            filename="threshold-development.zip",
            content_base64=_zip_base64(entries),
            start_date=date(2026, 8, 3),
            warning_acks=[],
        ),
    )

    assert result.activated is True
    assert {file.filename for file in result.files} == set(_ARTIFACT_FILENAMES)
    stored = repo.active_block()
    assert stored is not None
    assert stored.id == "block0.calibration"
    assert stored.schedule_start == "2026-08-03"
    assert stored.artifact == json.loads((CALIBRATION_FIXTURE / "block0.json").read_text())


@pytest.mark.parametrize("start_date", [None, "2026-02-30", "August 3, 2026"])
def test_package_import_requires_valid_explicit_start_date(start_date):
    payload = {
        "filename": "training.zip",
        "content_base64": _zip_base64(_calibration_entries()),
        "warning_acks": [],
    }
    if start_date is not None:
        payload["start_date"] = start_date

    with pytest.raises(ValidationError):
        ImportPackageRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("package_request", "message"),
    [
        (_request("not base64"), "valid base64"),
        (_request(b64encode(b"not a zip").decode("ascii")), "valid ZIP"),
        (_request(_zip_base64({"block.json": b"{}"}), filename="training.json"), ".zip"),
    ],
)
def test_invalid_package_container_is_rejected_without_activation(package_request, message):
    repo = SqliteTrainingRepository()

    with pytest.raises(ValueError, match=message):
        import_package(repo, package_request)

    assert repo.active_block() is None


@pytest.mark.parametrize(
    "member_name",
    [
        "../block0.json",
        "../README.md",
        "__MACOSX/../block0.json",
        "/block0.json",
        r"C:\training\block0.json",
    ],
)
def test_unsafe_member_path_is_rejected_without_activation(member_name):
    repo = SqliteTrainingRepository()

    with pytest.raises(ValueError, match="unsafe path"):
        import_package(repo, _request(_zip_base64({member_name: b"{}"})))

    assert repo.active_block() is None


def test_duplicate_json_basename_is_rejected_without_activation():
    repo = SqliteTrainingRepository()
    package = _zip_base64({"first/registry.json": b"{}", "second/registry.json": b"{}"})

    with pytest.raises(ValueError, match="duplicate JSON filename 'registry.json'"):
        import_package(repo, _request(package))

    assert repo.active_block() is None


def test_encrypted_member_is_rejected_without_activation():
    payload = bytearray(_zip_bytes({"block0.json": b"{}"}))
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        header = payload.index(signature)
        flags = int.from_bytes(payload[header + flag_offset : header + flag_offset + 2], "little")
        payload[header + flag_offset : header + flag_offset + 2] = (flags | 1).to_bytes(2, "little")
    repo = SqliteTrainingRepository()

    with pytest.raises(ValueError, match="encrypted"):
        import_package(repo, _request(b64encode(payload).decode("ascii")))

    assert repo.active_block() is None


def test_unsupported_compression_is_rejected_without_activation():
    payload = bytearray(_zip_bytes({"block0.json": b"{}"}))
    for signature, method_offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        header = payload.index(signature)
        payload[header + method_offset : header + method_offset + 2] = (99).to_bytes(2, "little")
    repo = SqliteTrainingRepository()

    with pytest.raises(ValueError, match="unsupported compression"):
        import_package(repo, _request(b64encode(payload).decode("ascii")))

    assert repo.active_block() is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not json", "valid JSON"),
        (b"[]", "JSON object"),
        (b"\xff", "UTF-8"),
    ],
)
def test_invalid_json_artifact_is_rejected_without_activation(content, message):
    repo = SqliteTrainingRepository()

    with pytest.raises(ValueError, match=message):
        import_package(repo, _request(_zip_base64({"block0.json": content})))

    assert repo.active_block() is None


def test_compressed_package_size_accepts_exact_limit_and_rejects_one_byte_over(monkeypatch):
    package_bytes = _zip_bytes({"block0.json": b"{}"})
    repo = SqliteTrainingRepository()
    monkeypatch.setattr(import_packages, "MAX_PACKAGE_BYTES", len(package_bytes))

    at_limit = import_package(repo, _request(b64encode(package_bytes).decode("ascii")))

    assert at_limit.activated is False
    monkeypatch.setattr(import_packages, "MAX_PACKAGE_BYTES", len(package_bytes) - 1)
    with pytest.raises(ValueError, match="compressed size limit"):
        import_package(repo, _request(b64encode(package_bytes).decode("ascii")))


def test_artifact_size_accepts_exact_limit_and_rejects_one_byte_over(monkeypatch):
    repo = SqliteTrainingRepository()
    monkeypatch.setattr(import_packages, "MAX_ARTIFACT_BYTES", 2)

    at_limit = import_package(repo, _request(_zip_base64({"block0.json": b"{}"})))

    assert at_limit.activated is False
    with pytest.raises(ValueError, match="artifact size limit"):
        import_package(repo, _request(_zip_base64({"block0.json": b"{}\n"})))


def test_total_artifact_size_accepts_exact_limit_and_rejects_one_byte_over(monkeypatch):
    repo = SqliteTrainingRepository()
    monkeypatch.setattr(import_packages, "MAX_TOTAL_ARTIFACT_BYTES", 4)

    at_limit = import_package(
        repo,
        _request(_zip_base64({"first.json": b"{}", "second.json": b"{}"})),
    )

    assert at_limit.activated is False
    with pytest.raises(ValueError, match="total artifact size limit"):
        import_package(
            repo,
            _request(_zip_base64({"first.json": b"{}", "second.json": b"{}\n"})),
        )


def test_json_member_count_accepts_exact_limit_and_rejects_one_over(monkeypatch):
    repo = SqliteTrainingRepository()
    monkeypatch.setattr(import_packages, "MAX_JSON_MEMBERS", 2)

    at_limit = import_package(
        repo,
        _request(_zip_base64({"first.json": b"{}", "second.json": b"{}"})),
    )

    assert at_limit.activated is False
    with pytest.raises(ValueError, match="JSON member limit"):
        import_package(
            repo,
            _request(
                _zip_base64(
                    {"first.json": b"{}", "second.json": b"{}", "third.json": b"{}"}
                )
            ),
        )


def test_archive_member_count_includes_ignored_files(monkeypatch):
    repo = SqliteTrainingRepository()
    monkeypatch.setattr(import_packages, "MAX_ARCHIVE_MEMBERS", 2)

    at_limit = import_package(
        repo,
        _request(_zip_base64({"README.md": b"notes", ".DS_Store": b"metadata"})),
    )

    assert at_limit.activated is False
    with pytest.raises(ValueError, match="archive member limit"):
        import_package(
            repo,
            _request(
                _zip_base64(
                    {
                        "README.md": b"notes",
                        ".DS_Store": b"metadata",
                        "review.txt": b"review",
                    }
                )
            ),
        )


def test_archive_member_preflight_does_not_trust_forged_eocd_count(monkeypatch):
    payload = bytearray(
        _zip_bytes(
            {
                "README.md": b"notes",
                ".DS_Store": b"metadata",
                "review.txt": b"review",
            }
        )
    )
    eocd = payload.rindex(b"PK\x05\x06")
    payload[eocd + 8 : eocd + 12] = (2).to_bytes(2, "little") * 2
    monkeypatch.setattr(import_packages, "MAX_ARCHIVE_MEMBERS", 2)

    def fail_if_zipfile_is_constructed(*_args, **_kwargs):
        raise AssertionError("member limit must be enforced before ZipFile construction")

    monkeypatch.setattr(import_packages, "ZipFile", fail_if_zipfile_is_constructed)

    with pytest.raises(ValueError, match="archive member limit"):
        import_package(
            repo=SqliteTrainingRepository(),
            request=_request(b64encode(payload).decode()),
        )


def test_package_can_be_resubmitted_with_lint_warning_acknowledged():
    raw_block = json.loads((CALIBRATION_FIXTURE / "block0.json").read_text())
    raw_block["baseline_tags"] = [
        tag for tag in raw_block["baseline_tags"] if tag != "protocol-change"
    ]
    entries = {
        **_calibration_entries(),
        "training-package/block0.json": json.dumps(raw_block).encode("utf-8"),
    }
    package = _zip_base64(entries)
    repo = SqliteTrainingRepository()

    unacked = import_package(repo, _request(package))

    assert unacked.activated is False
    assert unacked.lint_report is not None
    warning = next(item for item in unacked.lint_report.warnings if "L11" in item)
    acknowledged = import_package(
        repo,
        ImportPackageRequest(
            filename="training.zip",
            content_base64=package,
            start_date=date(2026, 8, 3),
            warning_acks=[warning],
        ),
    )
    assert acknowledged.activated is True
