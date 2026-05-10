"""Contracts for assistant conversations and evidence storage."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.contracts.base import (
    AutoTotalResponse,
    ConfidenceLevel,
    DefaultsRequired,
    StrictDefaultsRequired,
)

AssistantIntent = Literal[
    "experiment_review",
    "routine_adherence",
    "recovery_briefing",
    "open_ended_coaching",
]
AssistantResolvedEntityKind = Literal["experiment", "routine", "metric", "memory"]
AssistantMemoryRecordKind = Literal["entity_alias", "evidence_summary"]
PlanStatus = Literal["draft", "active", "completed"]
PlanItemCompletionState = Literal["pending", "in_progress", "completed", "skipped"]
ThreadStatus = Literal["active", "archived"]
EvidenceConfidence = ConfidenceLevel
AssistantMessageRole = Literal["user", "assistant", "system"]
AssistantRunStatus = Literal["running", "completed", "failed"]
AssistantRunTaskType = Literal["chat", "analysis", "planning"]


class Plan(DefaultsRequired):
    id: str
    title: str
    scope: str
    status: PlanStatus = "draft"
    source: str = "manual"
    goal: str | None = None
    markdown_body: str | None = None
    structured_outline_json: dict[str, object] = {}
    linked_experiment_ids: list[str] = []


class PlanItem(DefaultsRequired):
    id: str
    plan_id: str
    title: str
    date: str | None = None
    time_block: str | None = None
    instructions: str | None = None
    linked_routine_id: str | None = None
    completion_state: PlanItemCompletionState = "pending"
    completion_notes: str | None = None


class AssistantThread(DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"
    claude_session_id: str | None = None
    last_context_snapshot_id: str | None = None
    status: ThreadStatus = "active"
    last_message_at: str | None = None
    created_at: str | None = None


class AssistantMessage(DefaultsRequired):
    id: str
    thread_id: str
    role: AssistantMessageRole
    content_markdown: str
    structured_payload_json: dict[str, object] = {}
    evidence_refs_json: list[str] = []
    created_at: str | None = None


class AssistantRun(DefaultsRequired):
    id: str
    task_type: AssistantRunTaskType
    status: AssistantRunStatus
    thread_id: str | None = None
    context_snapshot_id: str | None = None
    claude_session_id: str | None = None
    command_json: dict[str, object] = {}
    stdout_path: str | None = None
    stderr_path: str | None = None
    usage_json: dict[str, object] = {}
    started_at: str | None = None
    finished_at: str | None = None


class ContextSnapshot(DefaultsRequired):
    id: str
    date_window_start: str | None = None
    date_window_end: str | None = None
    snapshot_json: dict[str, object] = {}
    summary_markdown: str | None = None
    created_at: str | None = None


class EvidenceCard(DefaultsRequired):
    id: str
    kind: str
    title: str
    summary: str
    metric: str | None = None
    window: str | None = None
    sample_count: int = 0
    confidence: EvidenceConfidence = "insufficient"
    caveats: list[str] = []
    payload_json: dict[str, object] = {}


class AssistantRouteDecision(StrictDefaultsRequired):
    """Deterministic intent-routing decision for one user message."""

    intent: AssistantIntent
    confidence: float = Field(ge=0.0, le=1.0)
    matched_signals: list[str] = Field(default_factory=list)


class AssistantResolvedEntity(StrictDefaultsRequired):
    """Domain entity resolved from a user message for evidence retrieval."""

    kind: AssistantResolvedEntityKind
    entity_id: str
    label: str
    score: float


class AssistantEvidenceItem(StrictDefaultsRequired):
    """One deterministic evidence record supplied to the assistant runtime."""

    kind: str
    source: str
    entity_id: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)


class AssistantEvidenceBundle(StrictDefaultsRequired):
    """Persisted evidence bundle for one user message and retrieval route."""

    id: str
    thread_id: str
    user_message_id: str
    intent: AssistantIntent
    entities: list[AssistantResolvedEntity] = Field(default_factory=list)
    items: list[AssistantEvidenceItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class AssistantMemoryRecord(StrictDefaultsRequired):
    """Persisted assistant memory record used for recall and alias resolution."""

    id: str
    kind: AssistantMemoryRecordKind
    entity_id: str | None = None
    alias_text: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AssistantThreadCreateRequest(DefaultsRequired):
    id: str
    title: str
    mode: str = "general"
    model: str = "sonnet"


class AssistantMessageCreateRequest(DefaultsRequired):
    id: str
    content: str


class AssistantThreadsResponse(AutoTotalResponse, items_field="threads"):
    threads: list[AssistantThread] = []


class AssistantMessagesResponse(AutoTotalResponse, items_field="messages"):
    messages: list[AssistantMessage] = []
