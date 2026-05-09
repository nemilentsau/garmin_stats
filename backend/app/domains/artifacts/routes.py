"""HTTP routes for artifact staging, bundles, and card templates."""

from fastapi import APIRouter

from app.bootstrap.container import build_container
from app.domains.artifacts.application.activation import activate_assistant_artifact
from app.domains.artifacts.application.bundles import (
    import_artifact_bundle,
    preview_artifact_bundle,
)
from app.domains.artifacts.application.cards import list_cards
from app.domains.artifacts.application.staging import (
    create_assistant_artifact,
    get_assistant_artifact,
    list_assistant_artifacts,
)
from app.domains.artifacts.contracts import (
    ArtifactBundleImportResponse,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
    AssistantArtifact,
    AssistantArtifactCreateRequest,
    AssistantArtifactsResponse,
)
from app.domains.routines.contracts import CardTemplatesResponse

assistant_artifacts_router = APIRouter(
    prefix="/api/assistant/artifacts",
    tags=["assistant-artifacts"],
)
assistant_artifact_bundles_router = APIRouter(
    prefix="/api/assistant/artifact-bundles",
    tags=["assistant-artifact-bundles"],
)
cards_router = APIRouter(prefix="/api/cards", tags=["cards"])


@assistant_artifacts_router.get("", response_model=AssistantArtifactsResponse)
def get_artifacts(kind: str | None = None, status: str | None = None):
    """Return assistant-authored artifacts."""
    return list_assistant_artifacts(
        build_container().artifacts_repo,
        kind=kind,
        status=status,
    )


@assistant_artifacts_router.get("/{artifact_id}", response_model=AssistantArtifact)
def get_artifact_detail(artifact_id: str):
    """Return a single assistant artifact."""
    return get_assistant_artifact(build_container().artifacts_repo, artifact_id)


@assistant_artifacts_router.post("", response_model=AssistantArtifact)
def post_artifact(request: AssistantArtifactCreateRequest):
    """Create and validate an assistant artifact draft."""
    container = build_container()
    return create_assistant_artifact(
        container.artifacts_repo,
        container.routines_repo,
        request,
    )


@assistant_artifacts_router.post("/{artifact_id}/activate", response_model=AssistantArtifact)
def post_activate_artifact(artifact_id: str):
    """Compile a validated artifact into live routine/card data."""
    container = build_container()
    return activate_assistant_artifact(
        container.artifacts_repo,
        container.routines_repo,
        artifact_id,
    )


@assistant_artifact_bundles_router.post(
    "/preview",
    response_model=ArtifactBundlePreviewResponse,
)
def post_preview_bundle(bundle: ArtifactBundleSpec):
    """Validate a structured artifact bundle without persisting anything."""
    container = build_container()
    return preview_artifact_bundle(container.artifacts_repo, container.routines_repo, bundle)


@assistant_artifact_bundles_router.post(
    "/import",
    response_model=ArtifactBundleImportResponse,
)
def post_import_bundle(bundle: ArtifactBundleSpec):
    """Import a validated bundle and auto-activate all artifacts."""
    container = build_container()
    result = import_artifact_bundle(container.artifacts_repo, container.routines_repo, bundle)
    # Activate card templates first because routine activation depends on them.
    card_ids = [d.artifact_id for d in result.deltas if d.kind == "card_template"]
    routine_ids = [d.artifact_id for d in result.deltas if d.kind == "routine_spec"]
    for artifact_id in card_ids + routine_ids:
        activate_assistant_artifact(
            container.artifacts_repo,
            container.routines_repo,
            artifact_id,
        )
    return result


@cards_router.get("", response_model=CardTemplatesResponse)
def get_cards(status: str | None = None):
    """Return compiled live card templates."""
    return list_cards(build_container().routines_repo, status=status)
