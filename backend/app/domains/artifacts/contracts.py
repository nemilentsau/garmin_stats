"""Contracts for assistant-authored artifacts and routine bundles."""

from __future__ import annotations

from typing import Literal

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)
from app.domains.routines.contracts import (
    RendererFamily,
    RoutineActivationAssignment,
    SlotName,
)

AssistantArtifactKind = Literal["routine_spec", "card_template", "capability_request"]
AssistantArtifactStatus = Literal["draft", "validated", "invalid", "activated"]
ArtifactBundleItemKind = Literal["card_template", "routine_spec"]
ArtifactBundleDeltaAction = Literal["create", "update"]


class TimerSegmentSpec(StrictDefaultsRequired):
    label: str
    duration_seconds: int


class RatingPromptSpec(StrictDefaultsRequired):
    key: str
    label: str
    scale_min: int | None = None
    scale_max: int | None = None


class ChecklistItemSpec(StrictDefaultsRequired):
    id: str
    label: str
    detail: str | None = None


class ExerciseItemSpec(StrictDefaultsRequired):
    id: str
    label: str
    detail: str | None = None
    reps: str | None = None
    duration_seconds: int | None = None


class TimerSessionPayloadSpec(StrictDefaultsRequired):
    duration_minutes: int | None = None
    pattern: str | None = None
    instructions: str | None = None
    segments: list[TimerSegmentSpec] = []
    rating_prompts: list[RatingPromptSpec] = []


class ChecklistBlockPayloadSpec(StrictDefaultsRequired):
    instructions: str | None = None
    items: list[ChecklistItemSpec] = []


class ExerciseBlockPayloadSpec(StrictDefaultsRequired):
    instructions: str | None = None
    exercises: list[ExerciseItemSpec] = []


class CardTemplateSpec(StrictDefaultsRequired):
    id: str
    name: str
    renderer: RendererFamily
    slot_default: SlotName
    summary: str | None = None
    tags: list[str] = []
    payload: dict[str, object] = {}


class RoutineSpec(StrictDefaultsRequired):
    id: str
    name: str
    start_date: str
    end_date: str | None = None
    status: EntityStatus = "active"
    tags: list[str] = []
    notes: str | None = None
    assignments: list[RoutineActivationAssignment] = []


class CapabilityRequestSpec(StrictDefaultsRequired):
    requested_renderer: str
    reason: str
    source_artifact_id: str | None = None
    payload_example_json: dict[str, object] = {}


class AssistantArtifact(DefaultsRequired):
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
    id: str
    kind: AssistantArtifactKind
    schema_version: int
    source_thread_id: str | None = None
    source_snapshot_id: str | None = None
    payload_json: dict[str, object] = {}


class AssistantArtifactsResponse(AutoTotalResponse, items_field="artifacts"):
    artifacts: list[AssistantArtifact] = []


class ArtifactBundleSpec(StrictDefaultsRequired):
    id: str
    name: str
    schema_version: int = 1
    description: str | None = None
    card_templates: list[CardTemplateSpec] = []
    routine_specs: list[RoutineSpec] = []


class ArtifactBundleIssue(DefaultsRequired):
    path: str
    message: str
    blocking: bool = True


class ArtifactBundleDelta(DefaultsRequired):
    artifact_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    action: ArtifactBundleDeltaAction
    summary: str


class ArtifactBundlePreviewResponse(DefaultsRequired):
    bundle_id: str
    bundle_name: str
    valid: bool = False
    issues: list[ArtifactBundleIssue] = []
    deltas: list[ArtifactBundleDelta] = []


class ArtifactBundleImportResponse(DefaultsRequired):
    bundle_id: str
    bundle_name: str
    imported_artifact_ids: list[str] = []
    total_imported: int = 0
    deltas: list[ArtifactBundleDelta] = []
