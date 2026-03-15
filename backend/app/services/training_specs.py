"""Validation and compilation for assistant-authored routine and card specs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from ..infra.database import (
    delete_routine_assignments,
    load_assistant_artifact,
    load_assistant_artifacts,
    load_card_template,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedule,
    load_routine_schedules,
    save_assistant_artifact,
    save_card_template,
    save_routine_assignment,
    save_routine_schedule,
)
from ..models import (
    AssistantArtifact,
    AssistantArtifactCreateRequest,
    AssistantArtifactsResponse,
    CapabilityRequestSpec,
    CardTemplate,
    CardTemplateSpec,
    CardTemplatesResponse,
    ChecklistBlockPayloadSpec,
    ExerciseBlockPayloadSpec,
    RoutineAssignment,
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
    RoutineSpec,
    TimerSessionPayloadSpec,
)

_PAYLOAD_MODELS = {
    "timer_session": TimerSessionPayloadSpec,
    "checklist_block": ChecklistBlockPayloadSpec,
    "exercise_block": ExerciseBlockPayloadSpec,
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _format_validation_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        msg = err["msg"]
        errors.append(f"{loc}: {msg}" if loc else msg)
    return errors


def _card_spec_artifact_by_card_id(card_id: str) -> AssistantArtifact | None:
    for artifact in load_assistant_artifacts(kind="card_template"):
        spec = artifact.payload_json
        if spec.get("id") == card_id and artifact.status in {"validated", "activated"}:
            return artifact
    return None


def _validate_card_template_payload(
    payload_json: dict[str, object],
) -> tuple[list[str], str | None]:
    requested_renderer = payload_json.get("renderer")
    if not isinstance(requested_renderer, str):
        return ["renderer: Field required"], None

    if requested_renderer not in _PAYLOAD_MODELS:
        return [f"renderer: Unsupported renderer family '{requested_renderer}'"], requested_renderer

    try:
        spec = CardTemplateSpec.model_validate(payload_json)
    except ValidationError as exc:
        return _format_validation_errors(exc), requested_renderer

    payload_model = _PAYLOAD_MODELS[spec.renderer]
    try:
        payload_model.model_validate(spec.payload)
    except ValidationError as exc:
        return _format_validation_errors(exc), requested_renderer

    return [], requested_renderer


def _validate_routine_spec_payload(payload_json: dict[str, object]) -> list[str]:
    try:
        spec = RoutineSpec.model_validate(payload_json)
    except ValidationError as exc:
        return _format_validation_errors(exc)

    errors: list[str] = []
    for assignment in spec.assignments:
        if spec.cadence == "weekly" and assignment.cycle_week != 1:
            errors.append(
                f"assignments.{assignment.id}.cycle_week: weekly routines must use cycle_week=1"
            )
        if spec.cadence == "biweekly" and assignment.cycle_week not in {1, 2}:
            errors.append(
                "assignments."
                f"{assignment.id}.cycle_week: biweekly routines must use cycle_week 1 or 2"
            )
        if (
            load_card_template(assignment.card_template_id) is None
            and _card_spec_artifact_by_card_id(assignment.card_template_id) is None
        ):
            errors.append(
                "assignments."
                f"{assignment.id}.card_template_id: unknown card template "
                f"'{assignment.card_template_id}'"
            )
    return errors


def _validate_capability_request_payload(payload_json: dict[str, object]) -> list[str]:
    try:
        CapabilityRequestSpec.model_validate(payload_json)
    except ValidationError as exc:
        return _format_validation_errors(exc)
    return []


def _system_capability_request(
    *,
    requested_renderer: str,
    source_artifact: AssistantArtifactCreateRequest,
) -> AssistantArtifact:
    now = _now_iso()
    artifact = AssistantArtifact(
        id=f"capreq-{uuid4().hex}",
        kind="capability_request",
        schema_version=1,
        status="draft",
        source_thread_id=source_artifact.source_thread_id,
        source_snapshot_id=source_artifact.source_snapshot_id,
        payload_json=CapabilityRequestSpec(
            requested_renderer=requested_renderer,
            reason=(
                f"Assistant draft '{source_artifact.id}' requested unsupported renderer "
                f"'{requested_renderer}'"
            ),
            source_artifact_id=source_artifact.id,
            payload_example_json=source_artifact.payload_json,
        ).model_dump(),
        created_at=now,
        updated_at=now,
    )
    save_assistant_artifact(artifact)
    return artifact


def create_assistant_artifact(request: AssistantArtifactCreateRequest) -> AssistantArtifact:
    now = _now_iso()
    errors: list[str] = []
    requested_renderer: str | None = None

    if request.kind == "card_template":
        errors, requested_renderer = _validate_card_template_payload(request.payload_json)
    elif request.kind == "routine_spec":
        errors = _validate_routine_spec_payload(request.payload_json)
    else:
        errors = _validate_capability_request_payload(request.payload_json)

    status = "validated" if not errors else "invalid"
    artifact = AssistantArtifact(
        id=request.id,
        kind=request.kind,
        schema_version=request.schema_version,
        status=status,
        source_thread_id=request.source_thread_id,
        source_snapshot_id=request.source_snapshot_id,
        payload_json=request.payload_json,
        validation_errors=errors,
        created_at=now,
        updated_at=now,
    )
    save_assistant_artifact(artifact)

    if (
        request.kind == "card_template"
        and requested_renderer
        and requested_renderer not in _PAYLOAD_MODELS
    ):
        _system_capability_request(requested_renderer=requested_renderer, source_artifact=request)

    return artifact


def list_assistant_artifacts(
    *,
    kind: str | None = None,
    status: str | None = None,
) -> AssistantArtifactsResponse:
    artifacts = load_assistant_artifacts(kind=kind, status=status)
    return AssistantArtifactsResponse(artifacts=artifacts, total=len(artifacts))


def get_assistant_artifact(artifact_id: str) -> AssistantArtifact:
    artifact = load_assistant_artifact(artifact_id)
    if artifact is None:
        raise LookupError(f"Assistant artifact {artifact_id} not found")
    return artifact


def _compile_card_template_artifact(artifact: AssistantArtifact) -> CardTemplate:
    spec = CardTemplateSpec.model_validate(artifact.payload_json)
    card = CardTemplate(
        id=spec.id,
        name=spec.name,
        renderer=spec.renderer,
        slot_default=spec.slot_default,
        summary=spec.summary,
        tags=spec.tags,
        payload_json=spec.payload,
        source_artifact_id=artifact.id,
    )
    save_card_template(card)
    return card


def _activate_card_template_dependency(card_id: str) -> None:
    if load_card_template(card_id) is not None:
        return

    dependency = _card_spec_artifact_by_card_id(card_id)
    if dependency is None:
        raise LookupError(f"Card template {card_id} is not available for activation")
    activate_assistant_artifact(dependency.id)


def _compile_routine_spec_artifact(artifact: AssistantArtifact) -> RoutineSchedule:
    spec = RoutineSpec.model_validate(artifact.payload_json)
    for assignment in spec.assignments:
        _activate_card_template_dependency(assignment.card_template_id)

    routine = RoutineSchedule(
        id=spec.id,
        name=spec.name,
        status=spec.status,
        cadence=spec.cadence,
        start_date=spec.start_date,
        end_date=spec.end_date,
        tags=spec.tags,
        notes=spec.notes,
        source_artifact_id=artifact.id,
    )
    save_routine_schedule(routine)
    delete_routine_assignments(routine.id)
    for assignment in spec.assignments:
        save_routine_assignment(
            RoutineAssignment(
                id=assignment.id,
                routine_id=routine.id,
                card_template_id=assignment.card_template_id,
                cycle_week=assignment.cycle_week,
                weekday=assignment.weekday,
                slot=assignment.slot,
                position=assignment.position,
                prescription_override_json=assignment.prescription_override_json,
            )
        )
    return routine


def activate_assistant_artifact(artifact_id: str) -> AssistantArtifact:
    artifact = get_assistant_artifact(artifact_id)
    if artifact.status == "activated":
        return artifact
    if artifact.status != "validated":
        raise ValueError(f"Assistant artifact {artifact_id} is not ready for activation")

    if artifact.kind == "card_template":
        _compile_card_template_artifact(artifact)
    elif artifact.kind == "routine_spec":
        _compile_routine_spec_artifact(artifact)
    else:
        raise ValueError("Capability requests cannot be activated")

    updated = artifact.model_copy(update={"status": "activated", "updated_at": _now_iso()})
    save_assistant_artifact(updated)
    return updated


def list_cards(status: str | None = None) -> CardTemplatesResponse:
    cards = load_card_templates(status=status)
    return CardTemplatesResponse(cards=cards, total=len(cards))


def list_routines(status: str | None = None) -> RoutineSchedulesResponse:
    routines = load_routine_schedules(status=status)
    return RoutineSchedulesResponse(routines=routines, total=len(routines))


def get_routine(routine_id: str) -> RoutineSchedule:
    routine = load_routine_schedule(routine_id)
    if routine is None:
        raise LookupError(f"Routine {routine_id} not found")
    return routine


def list_routine_assignments(routine_id: str) -> RoutineAssignmentsResponse:
    get_routine(routine_id)
    assignments = load_routine_assignments(routine_id=routine_id)
    return RoutineAssignmentsResponse(assignments=assignments, total=len(assignments))
