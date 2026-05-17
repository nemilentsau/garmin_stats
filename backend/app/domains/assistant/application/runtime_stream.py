"""Consume assistant runtime events and assemble the assistant message.

The runtime adapter emits provider-shaped dictionaries. This module normalizes
those into typed reply events and owns content assembly. Persistence and
wire-format JSON remain in the chat orchestration caller.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from uuid import uuid4

from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
)
from app.domains.assistant.dependencies import AssistantRuntime
from app.utils.timeutil import now_iso


@dataclass(frozen=True)
class RuntimeReplyDelta:
    """One assistant text chunk ready to emit to the route layer."""

    text: str


@dataclass(frozen=True)
class RuntimeReplyComplete:
    """Final assembled assistant message plus runtime session metadata."""

    assistant_message: AssistantMessage
    session_id: str | None


RuntimeReplyEvent = RuntimeReplyDelta | RuntimeReplyComplete


async def stream_runtime_reply(
    *,
    runtime: AssistantRuntime,
    evidence_bundle: AssistantEvidenceBundle,
    prior_messages: Sequence[AssistantMessage],
    memory_records: Sequence[AssistantMemoryRecord],
    user_message: str,
    model: str,
    thread_id: str,
) -> AsyncIterator[RuntimeReplyEvent]:
    """Yield typed deltas and then the assembled assistant message."""
    assistant_chunks: list[str] = []
    session_id: str | None = None

    fast_delta = _grounded_first_delta(evidence_bundle)
    if fast_delta:
        assistant_chunks.append(fast_delta)
        yield RuntimeReplyDelta(text=fast_delta)

    async for event in runtime.stream_chat(
        evidence_bundle=evidence_bundle,
        prior_messages=prior_messages,
        memory_records=memory_records,
        user_message=user_message,
        model=model,
    ):
        event_type = event.get("type")
        if event_type == "delta":
            delta = event.get("text")
            if isinstance(delta, str) and delta:
                assistant_chunks.append(delta)
                yield RuntimeReplyDelta(text=delta)
            continue
        if event_type == "done":
            candidate_session_id = event.get("session_id")
            if isinstance(candidate_session_id, str):
                session_id = candidate_session_id

    assistant_message = AssistantMessage(
        id=f"assistant-{uuid4().hex}",
        thread_id=thread_id,
        role="assistant",
        content_markdown="".join(assistant_chunks).strip(),
        evidence_refs_json=[evidence_bundle.id],
        created_at=now_iso(),
    )
    yield RuntimeReplyComplete(
        assistant_message=assistant_message,
        session_id=session_id,
    )


def _grounded_first_delta(bundle: AssistantEvidenceBundle) -> str:
    experiment_name: str | None = None
    exposure_count: int | None = None
    for item in bundle.items:
        if item.kind == "experiment":
            name = item.payload_json.get("name")
            if isinstance(name, str) and name:
                experiment_name = name
        if item.kind == "exposures":
            count = item.payload_json.get("count")
            if isinstance(count, int):
                exposure_count = count

    if experiment_name is None:
        return ""
    if exposure_count is None:
        return f"Grounded quick read: {experiment_name} is loaded from current experiment evidence."
    day_label = "day" if exposure_count == 1 else "days"
    return (
        f"Grounded quick read: {experiment_name} has "
        f"{exposure_count} logged exposure {day_label}."
    )
