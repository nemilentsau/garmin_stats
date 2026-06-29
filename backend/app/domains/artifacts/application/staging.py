"""Artifact staging use cases.

Staging accepts assistant-authored payloads, validates them against the artifact
schema family, and persists the result. Card templates are validated against the
``CardPayload`` union; invalid payloads are recorded with their error list.
"""

from __future__ import annotations

from app.domains.artifacts.contracts import (
    AssistantArtifact,
    AssistantArtifactCreateRequest,
    AssistantArtifactsResponse,
)
from app.domains.artifacts.dependencies import ArtifactRepository
from app.domains.routines.dependencies import RoutineRepository
from app.utils.timeutil import now_iso

from .validation import (
    validate_capability_request_payload,
    validate_card_template_payload,
    validate_routine_spec_payload,
)


def create_assistant_artifact(
    repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    request: AssistantArtifactCreateRequest,
) -> AssistantArtifact:
    """Validate and persist one assistant-authored artifact draft."""
    now = now_iso()
    errors: list[str] = []

    if request.kind == "card_template":
        errors, _ = validate_card_template_payload(request.payload_json)
    elif request.kind == "routine_spec":
        errors = validate_routine_spec_payload(repo, routines_repo, request.payload_json)
    else:
        errors = validate_capability_request_payload(request.payload_json)

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
    repo.save_assistant_artifact(artifact)
    return artifact


def list_assistant_artifacts(
    repo: ArtifactRepository,
    *,
    kind: str | None = None,
    status: str | None = None,
) -> AssistantArtifactsResponse:
    """Return staged assistant artifacts with optional kind/status filters."""
    artifacts = repo.list_assistant_artifacts(kind=kind, status=status)
    return AssistantArtifactsResponse(artifacts=artifacts)


def get_assistant_artifact(repo: ArtifactRepository, artifact_id: str) -> AssistantArtifact:
    """Return one staged assistant artifact or raise when it is unknown."""
    artifact = repo.get_assistant_artifact(artifact_id)
    if artifact is None:
        raise LookupError(f"Assistant artifact {artifact_id} not found")
    return artifact
