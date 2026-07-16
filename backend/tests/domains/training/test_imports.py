"""Single-shot v3 artifact import/activation tests against the block0 canon set.

`import_artifacts` is pure policy over the block0 canon artifacts: it never
mutates its inputs, and any failure — invalid contract, incomplete set, lint
error, un-acked warning — must leave storage untouched. The re-import test is
the idempotence keystone: importing the identical six files twice must leave
exactly one active block/registry/library row and three active bundle rows,
never duplicates. A second block of tests covers the `SqliteTrainingRepository`
capture-log methods, which no import path exercises.
"""

from __future__ import annotations

import json

from app.domains.training.adapters import SqliteTrainingRepository
from app.domains.training.application.imports import ImportFile, ImportRequest, import_artifacts
from app.domains.training.contracts import TrainingCardLog
from app.infra.sqlite import connect
from tests._architecture import REPO_ROOT

BLOCK0 = REPO_ROOT / "docs" / "routine-pivot" / "block0"
_BLOCK0_FILENAMES = [
    "block0.json",
    "running_v3.json",
    "strength_v3.json",
    "support_v3.json",
    "registry.json",
    "exercise_library.json",
]


def _load(name: str) -> dict:
    return json.loads((BLOCK0 / name).read_text(encoding="utf-8"))


def _block0_files(
    *,
    overrides: dict[str, dict] | None = None,
    exclude: set[str] | None = None,
) -> list[ImportFile]:
    """Build the six-file block0 import set, with optional per-file overrides/omissions."""
    overrides = overrides or {}
    exclude = exclude or set()
    return [
        ImportFile(filename=filename, content=overrides.get(filename) or _load(filename))
        for filename in _BLOCK0_FILENAMES
        if filename not in exclude
    ]


def _table_row_count(table: str) -> int:
    with connect() as con:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


# ---------- happy path + verbatim storage ----------


def test_full_import_activates_and_stores_artifacts_verbatim():
    repo = SqliteTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block0_files()))

    assert result.activated is True
    assert result.missing_kinds == []
    assert result.lint_report is not None
    assert result.lint_report.errors == []
    assert all(f.valid for f in result.files)

    stored_block = repo.active_block()
    assert stored_block is not None
    assert stored_block.status == "active"
    assert stored_block.artifact == _load("block0.json")
    assert stored_block.lint_report == result.lint_report

    stored_bundles = {
        bundle.id: bundle
        for bundle in repo.bundles_for(["running.v3", "strength.v3", "support.v3"])
    }
    assert set(stored_bundles) == {"running.v3", "strength.v3", "support.v3"}
    assert stored_bundles["running.v3"].status == "active"
    assert stored_bundles["running.v3"].artifact == _load("running_v3.json")

    registry = repo.registry()
    assert registry is not None
    assert registry.artifact == _load("registry.json")

    library = repo.library()
    assert library is not None
    assert library.artifact == _load("exercise_library.json")


# ---------- idempotent re-import (the keystone) ----------


def test_reimporting_identical_set_replaces_rows_without_duplicating():
    repo = SqliteTrainingRepository()
    import_artifacts(repo, ImportRequest(files=_block0_files()))
    result = import_artifacts(repo, ImportRequest(files=_block0_files()))

    assert result.activated is True
    assert _table_row_count("training_blocks") == 1
    assert _table_row_count("training_bundles") == 3
    assert _table_row_count("training_registry") == 1
    assert _table_row_count("training_exercise_library") == 1
    assert len(repo.bundles_for(["running.v3", "strength.v3", "support.v3"])) == 3


# ---------- incomplete set ----------


def test_incomplete_set_missing_registry_is_not_activated():
    repo = SqliteTrainingRepository()
    result = import_artifacts(repo, ImportRequest(files=_block0_files(exclude={"registry.json"})))

    assert result.activated is False
    assert result.missing_kinds == ["registry"]
    assert repo.active_block() is None


# ---------- lint error ----------


def test_lint_error_blocks_activation_and_stores_nothing():
    repo = SqliteTrainingRepository()
    raw_running = _load("running_v3.json")
    raw_running["owns"] = ["quad"]  # strength.v3 already owns "quad" -> L2 clash
    result = import_artifacts(
        repo, ImportRequest(files=_block0_files(overrides={"running_v3.json": raw_running}))
    )

    assert result.activated is False
    assert result.lint_report is not None
    assert any("L2" in e for e in result.lint_report.errors)
    assert repo.active_block() is None
    assert repo.registry() is None


# ---------- lint warning + ack gate ----------


def test_lint_warning_without_ack_blocks_but_acking_it_activates():
    repo = SqliteTrainingRepository()
    raw_block = _load("block0.json")
    raw_block["baseline_tags"] = [t for t in raw_block["baseline_tags"] if t != "protocol-change"]

    unacked = import_artifacts(
        repo, ImportRequest(files=_block0_files(overrides={"block0.json": raw_block}))
    )
    assert unacked.activated is False
    assert unacked.lint_report is not None
    warning = next(w for w in unacked.lint_report.warnings if "L11" in w)
    assert repo.active_block() is None

    acked = import_artifacts(
        repo,
        ImportRequest(
            files=_block0_files(overrides={"block0.json": raw_block}),
            warning_acks=[warning],
        ),
    )
    assert acked.activated is True
    assert repo.active_block() is not None


# ---------- unrecognized content ----------


def test_unknown_file_content_is_marked_invalid_and_blocks_activation():
    repo = SqliteTrainingRepository()
    files = [*_block0_files(), ImportFile(filename="mystery.json", content={"foo": "bar"})]
    result = import_artifacts(repo, ImportRequest(files=files))

    mystery = next(f for f in result.files if f.filename == "mystery.json")
    assert mystery.valid is False
    assert mystery.kind is None
    assert result.activated is False
    assert repo.active_block() is None


# ---------- duplicate kinds ----------


def test_duplicate_bundle_id_is_a_per_file_error_and_blocks_activation():
    repo = SqliteTrainingRepository()
    files = [
        *_block0_files(),
        ImportFile(filename="running_v3_dup.json", content=_load("running_v3.json")),
    ]
    result = import_artifacts(repo, ImportRequest(files=files))

    duplicate = next(f for f in result.files if f.filename == "running_v3_dup.json")
    assert duplicate.valid is False
    assert "duplicate" in duplicate.errors[0].lower()
    original = next(f for f in result.files if f.filename == "running_v3.json")
    assert original.valid is True
    assert result.activated is False
    assert repo.active_block() is None


def test_duplicate_registry_is_a_per_file_error_and_blocks_activation():
    repo = SqliteTrainingRepository()
    files = [
        *_block0_files(),
        ImportFile(filename="registry_dup.json", content=_load("registry.json")),
    ]
    result = import_artifacts(repo, ImportRequest(files=files))

    duplicate = next(f for f in result.files if f.filename == "registry_dup.json")
    assert duplicate.valid is False
    assert "duplicate" in duplicate.errors[0].lower()
    assert result.activated is False


# ---------- contract-invalid content ----------


def test_stray_bundle_not_referenced_by_block_blocks_activation():
    repo = SqliteTrainingRepository()
    extra_bundle = _load("support_v3.json")
    extra_bundle["id"] = "extra.v3"
    extra_bundle["name"] = "Unreferenced Extra Bundle"
    files = [*_block0_files(), ImportFile(filename="extra_v3.json", content=extra_bundle)]
    result = import_artifacts(repo, ImportRequest(files=files))

    assert result.activated is False
    extra_result = next(f for f in result.files if f.filename == "extra_v3.json")
    assert extra_result.valid is False
    assert extra_result.kind == "bundle"
    assert any(
        "extra.v3" in e and "not referenced by block" in e for e in extra_result.errors
    )
    assert repo.active_block() is None


def test_contract_invalid_bundle_content_is_marked_invalid():
    repo = SqliteTrainingRepository()
    raw_running = _load("running_v3.json")
    del raw_running["id"]
    result = import_artifacts(
        repo, ImportRequest(files=_block0_files(overrides={"running_v3.json": raw_running}))
    )

    running_file = next(f for f in result.files if f.filename == "running_v3.json")
    assert running_file.valid is False
    assert running_file.kind == "bundle"
    assert running_file.errors
    assert result.activated is False


# ---------- capture log repository methods ----------


def test_upsert_and_read_back_card_log():
    repo = SqliteTrainingRepository()
    log = TrainingCardLog(
        id="2026-07-06:running.v3:run.easy:d01",
        date="2026-07-06",
        occurrence_key="running.v3:run.easy:d01",
        status="completed",
    )
    repo.upsert_card_log(log)

    readback = repo.card_log("2026-07-06", "running.v3:run.easy:d01")
    assert readback is not None
    assert readback.status == "completed"


def test_card_logs_before_filters_to_strictly_earlier_dates():
    repo = SqliteTrainingRepository()
    repo.upsert_card_log(TrainingCardLog(id="2026-07-05:a", date="2026-07-05", occurrence_key="a"))
    repo.upsert_card_log(TrainingCardLog(id="2026-07-06:b", date="2026-07-06", occurrence_key="b"))
    repo.upsert_card_log(TrainingCardLog(id="2026-07-07:c", date="2026-07-07", occurrence_key="c"))

    logs = repo.card_logs_before("2026-07-06")
    assert [log.occurrence_key for log in logs] == ["a"]
