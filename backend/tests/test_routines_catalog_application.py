"""Tests for routines catalog use cases."""

from app.domains.routines.application.catalog import (
    get_routine,
    list_routine_assignments,
    list_routines,
)
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.models import AssistantArtifactCreateRequest
from app.services.training_specs import (
    activate_assistant_artifact,
    create_assistant_artifact,
)


def _card_request(card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": "timer_session",
            "slot_default": "morning",
            "summary": "Catalog fixture card",
            "tags": ["training"],
            "payload": {
                "duration_minutes": 10,
                "pattern": "5s in / 5s out",
                "instructions": "Stay relaxed.",
            },
        },
    )


def _routine_request(
    routine_id: str,
    *,
    card_id: str,
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Catalog fixture",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def test_list_routines_reads_live_schedules():
    repo = SqliteRoutineRepository()

    response = list_routines(repo, status="active")

    assert response.routines == []


def test_get_routine_and_assignments_read_same_routine():
    repo = SqliteRoutineRepository()
    card_artifact = create_assistant_artifact(_card_request("card-catalog"))
    activate_assistant_artifact(card_artifact.id)
    artifact = create_assistant_artifact(
        _routine_request("routine-catalog", card_id="card-catalog")
    )
    activate_assistant_artifact(artifact.id)

    routine = get_routine(repo, "routine-catalog")
    assignments = list_routine_assignments(repo, "routine-catalog")

    assert routine.id == "routine-catalog"
    assert assignments.assignments[0].routine_id == "routine-catalog"
