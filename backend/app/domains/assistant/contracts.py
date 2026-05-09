"""Contracts for assistant conversations and evidence storage."""

from __future__ import annotations

from typing import Literal

from app.contracts.base import AutoTotalResponse, DefaultsRequired

PlanStatus = Literal["draft", "active", "completed"]
PlanItemCompletionState = Literal["pending", "in_progress", "completed", "skipped"]
ThreadStatus = Literal["active", "archived"]
EvidenceConfidence = Literal["insufficient", "low", "moderate", "high"]
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
    total: int = 0


class AssistantMessagesResponse(AutoTotalResponse, items_field="messages"):
    messages: list[AssistantMessage] = []
    total: int = 0
