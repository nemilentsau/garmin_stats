"""Payload validation helpers for assistant-authored artifacts.

Validation keeps assistant payloads strict before they can be staged or bundled:
card templates must use a supported renderer payload, and routine specs must
reference known live or staged card templates.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

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
    """Flatten Pydantic errors into artifact validation messages."""
    errors: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        msg = err["msg"]
        errors.append(f"{loc}: {msg}" if loc else msg)
    return errors


def _try_validate[ModelT: BaseModel](
    model_cls: type[ModelT],
    payload: object,
) -> tuple[ModelT | None, list[str]]:
    """Validate ``payload`` against ``model_cls`` and flatten any errors."""
    try:
        return model_cls.model_validate(payload), []
    except ValidationError as exc:
        return None, format_validation_errors(exc)


def card_spec_artifact_by_card_id(
    repo: ArtifactRepository,
    card_id: str,
) -> AssistantArtifact | None:
    """Find a validated or activated card-template artifact by template id."""
    return repo.get_assistant_artifact_by_payload_id(
        "card_template", card_id, ("validated", "activated"),
    )


def validate_card_template_payload(
    payload_json: dict[str, object],
) -> tuple[list[str], str | None]:
    """Validate a card-template artifact and return errors plus renderer."""
    requested_renderer = payload_json.get("renderer")
    if not isinstance(requested_renderer, str):
        return ["renderer: Field required"], None

    if requested_renderer not in PAYLOAD_MODELS:
        return [f"renderer: Unsupported renderer family '{requested_renderer}'"], requested_renderer

    spec, errors = _try_validate(CardTemplateSpec, payload_json)
    if spec is None:
        return errors, requested_renderer

    _, payload_errors = _try_validate(PAYLOAD_MODELS[spec.renderer], spec.payload)
    return payload_errors, requested_renderer


def validate_routine_spec_payload(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    payload_json: dict[str, object],
    *,
    additional_card_ids: set[str] | None = None,
) -> list[str]:
    """Validate a routine spec against live and staged card templates."""
    spec, errors = _try_validate(RoutineSpec, payload_json)
    if spec is None:
        return errors

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
    """Validate a capability-request artifact payload."""
    _, errors = _try_validate(CapabilityRequestSpec, payload_json)
    return errors
