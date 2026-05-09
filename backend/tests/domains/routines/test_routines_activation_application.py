"""Routine artifact compilation tests for the routines domain."""

import pytest

import app.infra.database as db
from app.domains.artifacts.contracts import AssistantArtifact
from app.domains.routines.application.activation import compile_routine_artifact
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import load_routine_assignments, load_routine_schedule


def test_compile_routine_artifact_persists_schedule_and_assignments():
    repo = SqliteRoutineRepository()
    artifact = AssistantArtifact(
        id="artifact-routine-activation",
        kind="routine_spec",
        schema_version=1,
        status="validated",
        payload_json={
            "id": "routine-activation",
            "name": "Routine Activation",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Activation fixture",
            "assignments": [
                {
                    "id": "assignment-activation",
                    "card_template_id": "card-activation",
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                }
            ],
        },
        validation_errors=[],
        created_at="2026-03-01T00:00:00Z",
        updated_at="2026-03-01T00:00:00Z",
    )

    compile_routine_artifact(
        repo,
        artifact,
        activate_card_template_dependency=lambda *_args, **_kwargs: None,
    )

    assert load_routine_schedule("routine-activation") is not None
    assert (
        load_routine_assignments(routine_id="routine-activation")[0].id
        == "assignment-activation"
    )


def test_compile_routine_artifact_rolls_back_schedule_when_assignment_write_fails(monkeypatch):
    repo = SqliteRoutineRepository()
    artifact = AssistantArtifact(
        id="artifact-routine-atomic",
        kind="routine_spec",
        schema_version=1,
        status="validated",
        payload_json={
            "id": "routine-atomic",
            "name": "Routine Atomic",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Atomic fixture",
            "assignments": [
                {
                    "id": "assignment-atomic-1",
                    "card_template_id": "card-atomic-1",
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                },
                {
                    "id": "assignment-atomic-2",
                    "card_template_id": "card-atomic-2",
                    "day": 2,
                    "slot": "evening",
                    "position": 20,
                    "prescription_override_json": {},
                },
            ],
        },
        validation_errors=[],
        created_at="2026-03-01T00:00:00Z",
        updated_at="2026-03-01T00:00:00Z",
    )
    original_save = db._save_json_record_in_connection
    assignment_write_calls = 0

    def fail_on_second_assignment_write(*args, **kwargs):
        nonlocal assignment_write_calls
        if args[1] == "routine_assignments":
            assignment_write_calls += 1
            if assignment_write_calls == 2:
                raise RuntimeError("simulated assignment failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(db, "_save_json_record_in_connection", fail_on_second_assignment_write)

    with pytest.raises(RuntimeError, match="simulated assignment failure"):
        compile_routine_artifact(
            repo,
            artifact,
            activate_card_template_dependency=lambda *_args, **_kwargs: None,
        )

    assert load_routine_schedule("routine-atomic") is None
    assert load_routine_assignments(routine_id="routine-atomic") == []
