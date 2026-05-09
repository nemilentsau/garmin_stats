"""Routines schedule-window application tests."""

import pytest

from app.domains.artifacts.contracts import AssistantArtifactCreateRequest
from app.domains.routines.application.schedule_window import get_schedule_window
from app.domains.routines.contracts import CardOverride
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import save_card_override
from tests._artifacts_helpers import (
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
            "summary": "Schedule fixture card",
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
            "notes": "Schedule fixture routine",
            "assignments": [
                {
                    "id": f"{routine_id}-morning-late",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "morning",
                    "position": 30,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def _activate_card(card_id: str) -> None:
    artifact = create_assistant_artifact(_card_request(card_id))
    activate_assistant_artifact(artifact.id)


def _activate_routine(routine_id: str, *, card_id: str) -> None:
    artifact = create_assistant_artifact(_routine_request(routine_id, card_id=card_id))
    activate_assistant_artifact(artifact.id)


def test_schedule_window_returns_sorted_occurrences():
    _activate_card("card-schedule")
    _activate_routine("routine-schedule", card_id="card-schedule")

    repo = SqliteRoutineRepository()
    window = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)

    assert window.start_date == "2026-03-02"
    assert window.end_date == "2026-03-02"
    assert [occurrence.card_template_id for occurrence in window.days[0].occurrences] == [
        "card-schedule"
    ]


def test_schedule_window_applies_persisted_overrides():
    _activate_card("card-main")
    _activate_card("card-extra")
    _activate_routine("routine-main", card_id="card-main")

    repo = SqliteRoutineRepository()
    baseline = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)
    scheduled_occurrence = baseline.days[0].occurrences[0]
    save_card_override(
        CardOverride(
            id="override-extra",
            date="2026-03-02",
            action="replace",
            target_occurrence_key=scheduled_occurrence.occurrence_key,
            card_template_id="card-extra",
        )
    )
    window = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)

    assert [occurrence.card_template_id for occurrence in window.days[0].occurrences] == [
        "card-extra"
    ]


def test_schedule_window_rejects_non_positive_duration():
    repo = SqliteRoutineRepository()

    with pytest.raises(ValueError, match="duration_days must be greater than 0"):
        get_schedule_window(repo, start_date="2026-03-02", duration_days=0)
