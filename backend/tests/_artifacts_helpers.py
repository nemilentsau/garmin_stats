"""Test helpers for artifact use cases with explicit repositories."""

from __future__ import annotations

from app.domains.artifacts.application import artifacts as artifact_use_cases
from app.domains.artifacts.contracts import (
    ArtifactBundleImportResponse,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
    AssistantArtifact,
    AssistantArtifactCreateRequest,
)
from app.domains.artifacts.infra.sqlite_repository import SqliteArtifactRepository
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository


def create_assistant_artifact(request: AssistantArtifactCreateRequest) -> AssistantArtifact:
    return artifact_use_cases.create_assistant_artifact(SqliteArtifactRepository(), request)


def activate_assistant_artifact(artifact_id: str) -> AssistantArtifact:
    return artifact_use_cases.activate_assistant_artifact(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        artifact_id,
    )


def preview_artifact_bundle(bundle: ArtifactBundleSpec) -> ArtifactBundlePreviewResponse:
    return artifact_use_cases.preview_artifact_bundle(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        bundle,
    )


def import_artifact_bundle(bundle: ArtifactBundleSpec) -> ArtifactBundleImportResponse:
    return artifact_use_cases.import_artifact_bundle(
        SqliteArtifactRepository(),
        SqliteRoutineRepository(),
        bundle,
    )
