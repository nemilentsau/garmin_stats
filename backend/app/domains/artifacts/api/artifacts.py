"""Assistant artifact HTTP routes."""

from fastapi import APIRouter

from app.domains.artifacts.application.artifacts import (
    activate_assistant_artifact,
    create_assistant_artifact,
    get_assistant_artifact,
    list_assistant_artifacts,
)
from app.models import AssistantArtifact, AssistantArtifactCreateRequest, AssistantArtifactsResponse

router = APIRouter(prefix="/api/assistant/artifacts", tags=["assistant-artifacts"])


@router.get("", response_model=AssistantArtifactsResponse)
def get_artifacts(kind: str | None = None, status: str | None = None):
    """Return assistant-authored artifacts."""
    return list_assistant_artifacts(kind=kind, status=status)


@router.get("/{artifact_id}", response_model=AssistantArtifact)
def get_artifact_detail(artifact_id: str):
    """Return a single assistant artifact."""
    return get_assistant_artifact(artifact_id)


@router.post("", response_model=AssistantArtifact)
def post_artifact(request: AssistantArtifactCreateRequest):
    """Create and validate an assistant artifact draft."""
    return create_assistant_artifact(request)


@router.post("/{artifact_id}/activate", response_model=AssistantArtifact)
def post_activate_artifact(artifact_id: str):
    """Compile a validated artifact into live routine/card data."""
    return activate_assistant_artifact(artifact_id)
