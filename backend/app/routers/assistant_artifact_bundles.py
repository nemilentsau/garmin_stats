"""Assistant artifact bundle HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..models import (
    ArtifactBundleImportResponse,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
)
from ..services.training_specs import import_artifact_bundle, preview_artifact_bundle

router = APIRouter(prefix="/api/assistant/artifact-bundles", tags=["assistant-artifact-bundles"])


@router.post("/preview", response_model=ArtifactBundlePreviewResponse)
def post_preview_bundle(bundle: ArtifactBundleSpec):
    """Validate a structured artifact bundle without persisting anything."""
    return preview_artifact_bundle(bundle)


@router.post("/import", response_model=ArtifactBundleImportResponse)
def post_import_bundle(bundle: ArtifactBundleSpec):
    """Persist a validated structured artifact bundle as draft artifacts."""
    try:
        return import_artifact_bundle(bundle)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
