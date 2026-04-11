"""Internal assistant types used by the retrieval-first persistence layer."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AssistantIntent = Literal[
    "experiment_review",
    "routine_adherence",
    "recovery_briefing",
    "open_ended_coaching",
]
EXPERIMENT_REVIEW_TERMS = frozenset({"experiment", "trial", "study"})
AssistantResolvedEntityKind = Literal["experiment", "routine", "metric", "memory"]
AssistantMemoryRecordKind = Literal["entity_alias", "evidence_summary"]


class _AssistantInternalModel(BaseModel):
    """Strict base model for assistant-only persistence payloads."""

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
    )


class AssistantRouteDecision(_AssistantInternalModel):
    intent: AssistantIntent
    confidence: float = Field(ge=0.0, le=1.0)
    matched_signals: list[str] = Field(default_factory=list)


class AssistantResolvedEntity(_AssistantInternalModel):
    kind: AssistantResolvedEntityKind
    entity_id: str
    label: str
    score: float


class AssistantEvidenceItem(_AssistantInternalModel):
    kind: str
    source: str
    entity_id: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)


class AssistantEvidenceBundle(_AssistantInternalModel):
    id: str
    thread_id: str
    user_message_id: str
    intent: AssistantIntent
    entities: list[AssistantResolvedEntity] = Field(default_factory=list)
    items: list[AssistantEvidenceItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class AssistantMemoryRecord(_AssistantInternalModel):
    id: str
    kind: AssistantMemoryRecordKind
    entity_id: str | None = None
    alias_text: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
