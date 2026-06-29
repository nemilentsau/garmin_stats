"""Pydantic contracts owned by the artifacts domain.

These models describe staged assistant output, typed card payload specs,
bundle preview/import responses, and capability requests for unsupported
card types. Live routine/card contracts remain owned by the routines domain.
"""

from __future__ import annotations

from typing import Literal

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)
from app.domains.routines.contracts import (
    CardPayload,
    RoutineActivationAssignment,
    SlotName,
)

AssistantArtifactKind = Literal["routine_spec", "card_template", "capability_request"]
AssistantArtifactStatus = Literal["draft", "validated", "invalid", "activated"]
ArtifactBundleItemKind = Literal["card_template", "routine_spec"]
ArtifactBundleDeltaAction = Literal["create", "update"]


class CardTemplateSpec(StrictDefaultsRequired):
    """Assistant-authored card template draft before activation."""

    id: str
    name: str
    slot_default: SlotName
    summary: str | None = None
    tags: list[str] = []
    payload: CardPayload


class RoutineSpec(StrictDefaultsRequired):
    """Assistant-authored routine draft before activation."""

    id: str
    name: str
    start_date: str
    end_date: str | None = None
    status: EntityStatus = "active"
    tags: list[str] = []
    notes: str | None = None
    assignments: list[RoutineActivationAssignment] = []


class CapabilityRequestSpec(StrictDefaultsRequired):
    """Record of an unsupported card type or artifact capability request."""

    requested_card_type: str
    reason: str
    source_artifact_id: str | None = None
    payload_example_json: dict[str, object] = {}


class AssistantArtifact(DefaultsRequired):
    """Persisted assistant-authored artifact with validation state."""

    id: str
    kind: AssistantArtifactKind
    schema_version: int
    status: AssistantArtifactStatus = "draft"
    source_thread_id: str | None = None
    source_snapshot_id: str | None = None
    payload_json: dict[str, object] = {}
    validation_errors: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None


class AssistantArtifactCreateRequest(StrictDefaultsRequired):
    """Request body for staging one assistant-authored artifact."""

    id: str
    kind: AssistantArtifactKind
    schema_version: int
    source_thread_id: str | None = None
    source_snapshot_id: str | None = None
    payload_json: dict[str, object] = {}


class AssistantArtifactsResponse(AutoTotalResponse, items_field="artifacts"):
    """List response for staged assistant artifacts."""

    artifacts: list[AssistantArtifact] = []


class ArtifactBundleSpec(StrictDefaultsRequired):
    """Structured bundle of card and routine specs to preview or import."""

    id: str
    name: str
    schema_version: int = 1
    description: str | None = None
    card_templates: list[CardTemplateSpec] = []
    routine_specs: list[RoutineSpec] = []


class ArtifactBundleIssue(DefaultsRequired):
    """Validation issue found while previewing an artifact bundle."""

    path: str
    message: str
    blocking: bool = True


class ArtifactBundleDelta(DefaultsRequired):
    """Planned create/update change for one bundle artifact target."""

    artifact_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    action: ArtifactBundleDeltaAction
    summary: str


class ArtifactBundlePreviewResponse(DefaultsRequired):
    """Preview result for a structured artifact bundle."""

    bundle_id: str
    bundle_name: str
    valid: bool = False
    issues: list[ArtifactBundleIssue] = []
    deltas: list[ArtifactBundleDelta] = []


class ArtifactBundleImportResponse(DefaultsRequired):
    """Import result for a structured artifact bundle."""

    bundle_id: str
    bundle_name: str
    imported_artifact_ids: list[str] = []
    total_imported: int = 0
    deltas: list[ArtifactBundleDelta] = []
