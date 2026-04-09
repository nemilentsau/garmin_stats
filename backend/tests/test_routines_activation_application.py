"""Routine artifact compilation tests for the routines domain."""

from app.domains.routines.application.activation import compile_routine_artifact
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import load_routine_assignments, load_routine_schedule
from app.models import AssistantArtifact


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
