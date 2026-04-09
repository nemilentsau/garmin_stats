"""Tests for routines today use cases."""

import pytest

from app.domains.routines.application.today import (
    get_card_log_range,
    get_today,
    upsert_today_card_log,
)
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.models import (
    AssistantArtifactCreateRequest,
    CardLog,
    TodayCardLogUpdateRequest,
)
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
            "slot_default": "evening",
            "summary": "Today fixture card",
            "tags": ["training"],
            "payload": {
                "duration_minutes": 10,
                "pattern": "5s in / 5s out",
                "instructions": "Stay relaxed.",
            },
        },
    )


def _routine_request(routine_id: str, *, card_id: str) -> AssistantArtifactCreateRequest:
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
            "notes": "Today fixture routine",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "evening",
                    "position": 20,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def test_get_today_returns_grouped_slots_and_stats():
    card_artifact = create_assistant_artifact(_card_request("card-today"))
    activate_assistant_artifact(card_artifact.id)
    routine_artifact = create_assistant_artifact(
        _routine_request("routine-today", card_id="card-today")
    )
    activate_assistant_artifact(routine_artifact.id)

    repo = SqliteRoutineRepository()
    response = get_today(repo, date="2026-03-02")

    assert response.date == "2026-03-02"
    assert response.stats.total == 1
    assert response.slots[2].cards[0].card_template_id == "card-today"


def test_get_card_log_range_excludes_pending_entries():
    repo = SqliteRoutineRepository()
    repo.save_card_log(
        CardLog(
            id="card-log:2026-03-02:pending",
            date="2026-03-02",
            occurrence_key="scheduled:pending:2026-03-02",
            card_template_id="card-pending",
            assignment_id="assignment-pending",
            status="pending",
            actual_json={},
            notes=None,
        )
    )
    repo.save_card_log(
        CardLog(
            id="card-log:2026-03-02:completed",
            date="2026-03-02",
            occurrence_key="scheduled:completed:2026-03-02",
            card_template_id="card-completed",
            assignment_id="assignment-completed",
            status="completed",
            actual_json={"actual_minutes": 10},
            notes="Done",
        )
    )

    response = get_card_log_range(repo, start_date="2026-03-02", end_date="2026-03-02")

    assert len(response.entries) == 1
    assert response.entries[0].occurrence_key == "scheduled:completed:2026-03-02"
    assert response.entries[0].status == "completed"


def test_upsert_today_card_log_validates_occurrence_identity():
    repo = SqliteRoutineRepository()
    request = TodayCardLogUpdateRequest(
        card_template_id="wrong-card",
        assignment_id=None,
        status="completed",
        actual_json={},
        notes=None,
    )

    with pytest.raises(LookupError, match="Today occurrence missing not found"):
        upsert_today_card_log(repo, date="2026-03-02", occurrence_key="missing", request=request)


def test_upsert_today_card_log_rejects_assignment_mismatch():
    card_artifact = create_assistant_artifact(_card_request("card-assignment"))
    activate_assistant_artifact(card_artifact.id)
    routine_artifact = create_assistant_artifact(
        _routine_request("routine-assignment", card_id="card-assignment")
    )
    activate_assistant_artifact(routine_artifact.id)

    repo = SqliteRoutineRepository()
    today = get_today(repo, date="2026-03-02")
    scheduled_card = today.slots[2].cards[0]

    with pytest.raises(ValueError, match="Assignment id does not match"):
        upsert_today_card_log(
            repo,
            date="2026-03-02",
            occurrence_key=scheduled_card.occurrence_key,
            request=TodayCardLogUpdateRequest(
                card_template_id=scheduled_card.card_template_id,
                assignment_id="wrong-assignment",
                status="completed",
                actual_json={},
                notes=None,
            ),
        )
