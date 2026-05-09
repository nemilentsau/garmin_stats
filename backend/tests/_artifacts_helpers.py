"""Test helpers for artifact use cases with explicit repositories."""

from __future__ import annotations

from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.artifacts.application.activation import (
    activate_assistant_artifact as activate_artifact_use_case,
)
from app.domains.artifacts.application.bundles import (
    import_artifact_bundle as import_bundle_use_case,
)
from app.domains.artifacts.application.bundles import (
    preview_artifact_bundle as preview_bundle_use_case,
)
from app.domains.artifacts.application.staging import (
    create_assistant_artifact as create_artifact_use_case,
)
from app.domains.artifacts.contracts import (
    ArtifactBundleImportResponse,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
    AssistantArtifact,
    AssistantArtifactCreateRequest,
)
from app.domains.routines.adapters import SqliteRoutineRepository
from app.domains.routines.application.activation import compile_routine_activation


def create_assistant_artifact(request: AssistantArtifactCreateRequest) -> AssistantArtifact:
    return create_artifact_use_case(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        request,
    )


def activate_assistant_artifact(artifact_id: str) -> AssistantArtifact:
    return activate_artifact_use_case(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        compile_routine_activation,
        artifact_id,
    )


def preview_artifact_bundle(bundle: ArtifactBundleSpec) -> ArtifactBundlePreviewResponse:
    return preview_bundle_use_case(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        bundle,
    )


def import_artifact_bundle(bundle: ArtifactBundleSpec) -> ArtifactBundleImportResponse:
    return import_bundle_use_case(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        bundle,
    )
