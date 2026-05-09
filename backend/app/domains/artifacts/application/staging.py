"""Artifact staging use cases.

Staging accepts assistant-authored payloads, validates them against the artifact
schema family, and records unsupported renderer requests as capability-request
artifacts for later product decisions.
"""

from __future__ import annotations

from uuid import uuid4

from app.domains.artifacts.contracts import (
    AssistantArtifact,
    AssistantArtifactCreateRequest,
    AssistantArtifactsResponse,
    CapabilityRequestSpec,
)
from app.domains.artifacts.dependencies import ArtifactRepository
from app.domains.routines.dependencies import RoutineRepository
from app.utils.timeutil import now_iso

from .validation import (
    PAYLOAD_MODELS,
    validate_capability_request_payload,
    validate_card_template_payload,
    validate_routine_spec_payload,
)


def _system_capability_request(
    repo: ArtifactRepository,
    *,
    requested_renderer: str,
    source_artifact: AssistantArtifactCreateRequest,
) -> AssistantArtifact:
    now = now_iso()
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
    repo.save_assistant_artifact(artifact)
    return artifact


def create_assistant_artifact(
    repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    request: AssistantArtifactCreateRequest,
) -> AssistantArtifact:
    now = now_iso()
    errors: list[str] = []
    requested_renderer: str | None = None

    if request.kind == "card_template":
        errors, requested_renderer = validate_card_template_payload(request.payload_json)
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

    if (
        request.kind == "card_template"
        and requested_renderer
        and requested_renderer not in PAYLOAD_MODELS
    ):
        _system_capability_request(
            repo,
            requested_renderer=requested_renderer,
            source_artifact=request,
        )

    return artifact


def list_assistant_artifacts(
    repo: ArtifactRepository,
    *,
    kind: str | None = None,
    status: str | None = None,
) -> AssistantArtifactsResponse:
    artifacts = repo.list_assistant_artifacts(kind=kind, status=status)
    return AssistantArtifactsResponse(artifacts=artifacts)


def get_assistant_artifact(repo: ArtifactRepository, artifact_id: str) -> AssistantArtifact:
    artifact = repo.get_assistant_artifact(artifact_id)
    if artifact is None:
        raise LookupError(f"Assistant artifact {artifact_id} not found")
    return artifact
