"""Assistant artifact bundle HTTP routes."""

from fastapi import APIRouter

from ..models import (
    ArtifactBundleImportResponse,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
)
from ..services.training_specs import (
    activate_assistant_artifact,
    import_artifact_bundle,
    preview_artifact_bundle,
)

router = APIRouter(prefix="/api/assistant/artifact-bundles", tags=["assistant-artifact-bundles"])


@router.post("/preview", response_model=ArtifactBundlePreviewResponse)
def post_preview_bundle(bundle: ArtifactBundleSpec):
    """Validate a structured artifact bundle without persisting anything."""
    return preview_artifact_bundle(bundle)


@router.post("/import", response_model=ArtifactBundleImportResponse)
def post_import_bundle(bundle: ArtifactBundleSpec):
    """Import a validated bundle and auto-activate all artifacts."""
    result = import_artifact_bundle(bundle)
    # Activate card templates first (routines depend on them), then routines.
    card_ids = [d.artifact_id for d in result.deltas if d.kind == "card_template"]
    routine_ids = [d.artifact_id for d in result.deltas if d.kind == "routine_spec"]
    for artifact_id in card_ids + routine_ids:
        activate_assistant_artifact(artifact_id)
    return result
