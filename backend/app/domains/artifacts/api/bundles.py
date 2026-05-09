"""Assistant artifact bundle HTTP routes."""

from fastapi import APIRouter

from app.bootstrap.container import build_container
from app.domains.artifacts.application.artifacts import (
    activate_assistant_artifact,
    import_artifact_bundle,
    preview_artifact_bundle,
)
from app.domains.artifacts.contracts import (
    ArtifactBundleImportResponse,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
)

router = APIRouter(prefix="/api/assistant/artifact-bundles", tags=["assistant-artifact-bundles"])


@router.post("/preview", response_model=ArtifactBundlePreviewResponse)
def post_preview_bundle(bundle: ArtifactBundleSpec):
    """Validate a structured artifact bundle without persisting anything."""
    container = build_container()
    return preview_artifact_bundle(container.artifacts_repo, container.routines_repo, bundle)


@router.post("/import", response_model=ArtifactBundleImportResponse)
def post_import_bundle(bundle: ArtifactBundleSpec):
    """Import a validated bundle and auto-activate all artifacts."""
    container = build_container()
    result = import_artifact_bundle(container.artifacts_repo, container.routines_repo, bundle)
    # Activate card templates first (routines depend on them), then routines.
    card_ids = [d.artifact_id for d in result.deltas if d.kind == "card_template"]
    routine_ids = [d.artifact_id for d in result.deltas if d.kind == "routine_spec"]
    for artifact_id in card_ids + routine_ids:
        activate_assistant_artifact(container.artifacts_repo, container.routines_repo, artifact_id)
    return result
