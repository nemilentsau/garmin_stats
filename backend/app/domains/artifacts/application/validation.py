"""Payload validation helpers for assistant-authored artifacts."""

from __future__ import annotations

from pydantic import ValidationError

from app.domains.artifacts.contracts import (
    AssistantArtifact,
    CapabilityRequestSpec,
    CardTemplateSpec,
    ChecklistBlockPayloadSpec,
    ExerciseBlockPayloadSpec,
    RoutineSpec,
    TimerSessionPayloadSpec,
)
from app.domains.artifacts.dependencies import ArtifactRepository
from app.domains.routines.dependencies import RoutineRepository

PAYLOAD_MODELS = {
    "timer_session": TimerSessionPayloadSpec,
    "checklist_block": ChecklistBlockPayloadSpec,
    "exercise_block": ExerciseBlockPayloadSpec,
}


def format_validation_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        msg = err["msg"]
        errors.append(f"{loc}: {msg}" if loc else msg)
    return errors


def card_spec_artifact_by_card_id(
    repo: ArtifactRepository,
    card_id: str,
) -> AssistantArtifact | None:
    return repo.get_assistant_artifact_by_payload_id(
        "card_template", card_id, ("validated", "activated"),
    )


def validate_card_template_payload(
    payload_json: dict[str, object],
) -> tuple[list[str], str | None]:
    requested_renderer = payload_json.get("renderer")
    if not isinstance(requested_renderer, str):
        return ["renderer: Field required"], None

    if requested_renderer not in PAYLOAD_MODELS:
        return [f"renderer: Unsupported renderer family '{requested_renderer}'"], requested_renderer

    try:
        spec = CardTemplateSpec.model_validate(payload_json)
    except ValidationError as exc:
        return format_validation_errors(exc), requested_renderer

    payload_model = PAYLOAD_MODELS[spec.renderer]
    try:
        payload_model.model_validate(spec.payload)
    except ValidationError as exc:
        return format_validation_errors(exc), requested_renderer

    return [], requested_renderer


def validate_routine_spec_payload(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    payload_json: dict[str, object],
    *,
    additional_card_ids: set[str] | None = None,
) -> list[str]:
    try:
        spec = RoutineSpec.model_validate(payload_json)
    except ValidationError as exc:
        return format_validation_errors(exc)

    errors: list[str] = []
    additional_card_ids = additional_card_ids or set()
    for assignment in spec.assignments:
        if assignment.day < 1:
            errors.append(f"assignments.{assignment.id}.day: must be >= 1")
        if (
            assignment.card_template_id not in additional_card_ids
            and routines_repo.get_card_template(assignment.card_template_id) is None
            and card_spec_artifact_by_card_id(artifact_repo, assignment.card_template_id) is None
        ):
            errors.append(
                "assignments."
                f"{assignment.id}.card_template_id: unknown card template "
                f"'{assignment.card_template_id}'"
            )
    return errors


def validate_capability_request_payload(payload_json: dict[str, object]) -> list[str]:
    try:
        CapabilityRequestSpec.model_validate(payload_json)
    except ValidationError as exc:
        return format_validation_errors(exc)
    return []
