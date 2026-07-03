"""Container-wired wrappers around routine application services for tests."""

from app.bootstrap.container import build_container
from app.domains.artifacts.contracts import AssistantArtifactCreateRequest
from app.domains.routines.adapters import _STORE as _ROUTINES_STORE
from app.domains.routines.application.schedule_window import (
    get_schedule_window as _get_schedule_window,
)
from app.domains.routines.application.today import (
    get_today as _get_today,
)
from app.domains.routines.application.today import (
    upsert_today_card_log as _upsert_today_card_log,
)
from app.domains.routines.contracts import (
    CardOverride,
    RoutineAssignment,
    RoutineSchedule,
    TodayCardLogUpdateRequest,
)
from tests._artifacts_helpers import (
    activate_assistant_artifact,
    create_assistant_artifact,
)


def routine_card_request(
    card_id: str,
    *,
    name: str | None = None,
    slot_default: str = "morning",
    summary: str | None = None,
    tags: list[str] | None = None,
    payload: dict[str, object] | None = None,
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": name or f"Card {card_id}",
            "slot_default": slot_default,
            "summary": summary or f"Summary for {card_id}",
            "tags": tags or ["training"],
            "payload": payload
            or {
                "card_type": "breath_timer",
                "duration_minutes": 10,
                "pattern_label": "5s in / 5s out",
                "instructions": "Stay relaxed.",
            },
        },
    )


def routine_assignment_spec(
    assignment_id: str,
    *,
    card_template_id: str,
    day: int = 1,
    slot: str = "morning",
    position: int = 10,
    prescription_override_json: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": assignment_id,
        "card_template_id": card_template_id,
        "day": day,
        "slot": slot,
        "position": position,
        "prescription_override_json": prescription_override_json or {},
    }


def routine_spec_request(
    routine_id: str,
    *,
    assignments: list[dict[str, object]],
    start_date: str = "2026-03-02",
    end_date: str | None = None,
    status: str = "active",
    name: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": name or f"Routine {routine_id}",
            "start_date": start_date,
            "end_date": end_date,
            "status": status,
            "tags": tags or ["training"],
            "notes": notes or f"Schedule for {routine_id}",
            "assignments": assignments,
        },
    )


def activate_routine_card(
    card_id: str,
    *,
    name: str | None = None,
    slot_default: str = "morning",
) -> None:
    artifact = create_assistant_artifact(
        routine_card_request(card_id, name=name, slot_default=slot_default)
    )
    activate_assistant_artifact(artifact.id)


def activate_routine_spec(
    routine_id: str,
    *,
    assignments: list[dict[str, object]],
    start_date: str = "2026-03-02",
    end_date: str | None = None,
    status: str = "active",
) -> None:
    artifact = create_assistant_artifact(
        routine_spec_request(
            routine_id,
            assignments=assignments,
            start_date=start_date,
            end_date=end_date,
            status=status,
        )
    )
    activate_assistant_artifact(artifact.id)


def live_routine(routine_id: str) -> RoutineSchedule:
    return RoutineSchedule(
        id=routine_id,
        name=f"Routine {routine_id}",
        start_date="2026-03-02",
        status="active",
        tags=["training"],
        notes="Catalog fixture",
    )


def live_routine_assignment(assignment_id: str, *, routine_id: str) -> RoutineAssignment:
    return RoutineAssignment(
        id=assignment_id,
        routine_id=routine_id,
        card_template_id="card-catalog",
        date="2026-03-02",
        slot="morning",
        position=10,
        prescription_override_json={},
    )


def get_schedule_window(start_date: str, duration_days: int = 14):
    return _get_schedule_window(
        build_container().routines_repo,
        start_date=start_date,
        duration_days=duration_days,
    )


def get_today(date: str):
    return _get_today(build_container().routines_repo, date=date)


def upsert_today_card_log(
    date: str,
    occurrence_key: str,
    request: TodayCardLogUpdateRequest,
):
    container = build_container()
    return _upsert_today_card_log(
        container.routines_repo,
        date=date,
        occurrence_key=occurrence_key,
        request=request,
        observer=container.experiment_exposure_sync,
    )


def persist_card_override(override: CardOverride) -> None:
    """Seed a persisted card override without exposing a production write API."""
    _ROUTINES_STORE.save(
        "card_overrides",
        override.id,
        override.model_dump_json(),
        extra_columns={
            "override_date": override.date,
            "action": override.action,
            "target_occurrence_key": override.target_occurrence_key,
        },
    )
