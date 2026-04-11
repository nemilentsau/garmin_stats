"""Retrieval-first assistant chat orchestration."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel

from app.domains.assistant.application.entity_resolution import resolve_entities
from app.domains.assistant.application.evidence import build_evidence_bundle
from app.domains.assistant.application.ports import (
    AssistantConversationStore,
    AssistantReadModelStore,
    AssistantRetrievalStore,
    AssistantRuntime,
)
from app.domains.assistant.application.router import route_user_query
from app.domains.assistant.application.types import AssistantEvidenceBundle
from app.models import AssistantMessage, AssistantMessageCreateRequest, AssistantRun
from app.utils.timeutil import now_iso

_MAX_MEMORY_RECORDS = 5


class _RetrievalStoreAdapter:
    """Bridge read-model data with backend-owned recall records."""

    def __init__(
        self,
        *,
        read_store: AssistantReadModelStore,
        conversation_store: AssistantConversationStore,
    ) -> None:
        self._read_store = read_store
        self._conversation_store = conversation_store

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ):
        return self._conversation_store.list_evidence_bundles(thread_id=thread_id, last_n=last_n)

    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
    ):
        return self._conversation_store.list_memory_records(kind=kind, last_n=last_n)

    def __getattr__(self, item: str) -> object:
        return getattr(self._read_store, item)


def _json_line(payload: dict[str, object]) -> str:
    return json.dumps(payload) + "\n"


def _model_for_thread(thread: object) -> str:
    if isinstance(thread, dict):
        model = thread.get("model")
        return model if isinstance(model, str) and model else "sonnet"
    model = getattr(thread, "model", "sonnet")
    if isinstance(model, str) and model:
        return model
    return "sonnet"


def _message_to_dict(message: object) -> dict[str, object]:
    if isinstance(message, dict):
        return dict(message)
    if isinstance(message, BaseModel):
        dumped = message.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    return {}


def _thread_id(thread: object) -> str:
    if isinstance(thread, dict):
        value = thread.get("id")
        if isinstance(value, str):
            return value
    value = getattr(thread, "id", None)
    if isinstance(value, str):
        return value
    raise ValueError("thread id is missing")


def _save_thread_state(
    *,
    repo: AssistantConversationStore,
    thread: object,
    last_message_at: str,
    snapshot_id: str | None = None,
    session_id: str | None = None,
    persist: bool = True,
) -> object:
    if isinstance(thread, dict):
        updated = dict(thread)
        updated["last_message_at"] = last_message_at
        if snapshot_id is not None:
            updated["last_context_snapshot_id"] = snapshot_id
        if session_id is not None:
            updated["claude_session_id"] = session_id
        if persist:
            cast(Any, repo).save_thread(updated)
        return updated

    if isinstance(thread, BaseModel):
        updates: dict[str, object] = {"last_message_at": last_message_at}
        if snapshot_id is not None:
            updates["last_context_snapshot_id"] = snapshot_id
        if session_id is not None:
            updates["claude_session_id"] = session_id
        updated_model = thread.model_copy(update=updates)
        if persist:
            cast(Any, repo).save_thread(updated_model)
        return updated_model

    raise TypeError("unsupported thread type for state persistence")


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
        return f"Grounded quick read: {experiment_name} is loaded from your saved evidence."
    day_label = "day" if exposure_count == 1 else "days"
    return (
        f"Grounded quick read: {experiment_name} has {exposure_count} logged exposure {day_label}; "
        "I will refine this with your thread history."
    )


async def stream_reply(
    *,
    repo: AssistantConversationStore,
    read_store: AssistantReadModelStore,
    runtime: AssistantRuntime,
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    run: AssistantRun | None = None
    thread: object | None = None
    evidence_bundle: AssistantEvidenceBundle | None = None
    assistant_chunks: list[str] = []
    session_id: str | None = None

    try:
        thread = repo.get_thread(thread_id)
        if thread is None:
            raise LookupError(f"Assistant thread '{thread_id}' not found")

        prior_messages = [_message_to_dict(message) for message in repo.list_messages(thread_id)]
        user_message = AssistantMessage(
            id=request.id,
            thread_id=thread_id,
            role="user",
            content_markdown=request.content,
            created_at=now_iso(),
        )
        repo.save_message(user_message)
        thread = _save_thread_state(
            repo=repo,
            thread=thread,
            last_message_at=user_message.created_at or now_iso(),
        )

        memory_records = list(repo.list_memory_records(last_n=_MAX_MEMORY_RECORDS))
        route = route_user_query(request.content)
        entities = resolve_entities(
            store=read_store,
            memory=memory_records,
            route=route,
            query=request.content,
        )
        evidence_bundle = build_evidence_bundle(
            store=cast(
                AssistantRetrievalStore,
                _RetrievalStoreAdapter(read_store=read_store, conversation_store=repo),
            ),
            route=route,
            entities=entities,
            thread_id=_thread_id(thread),
            user_message_id=request.id,
        )

        run = AssistantRun(
            id=f"run-{uuid4().hex}",
            task_type="chat",
            status="running",
            thread_id=_thread_id(thread),
            context_snapshot_id=evidence_bundle.id,
            command_json={
                "model": _model_for_thread(thread),
                "intent": route.intent,
                "confidence": route.confidence,
                "matched_signals": list(route.matched_signals),
            },
            started_at=now_iso(),
        )
        repo.save_run(run)
        repo.save_evidence_bundle(evidence_bundle)

        fast_delta = _grounded_first_delta(evidence_bundle)
        if fast_delta:
            assistant_chunks.append(fast_delta)
            yield _json_line({"type": "delta", "text": fast_delta})

        async for event in runtime.stream_chat(
            evidence_bundle=evidence_bundle,
            prior_messages=prior_messages,
            memory_records=memory_records,
            user_message=request.content,
            model=_model_for_thread(thread),
        ):
            event_type = event.get("type")
            if event_type == "delta":
                delta = event.get("text")
                if isinstance(delta, str) and delta:
                    assistant_chunks.append(delta)
                    yield _json_line({"type": "delta", "text": delta})
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
        thread = _save_thread_state(
            repo=repo,
            thread=thread,
            last_message_at=assistant_message.created_at or now_iso(),
            snapshot_id=evidence_bundle.id,
            session_id=session_id,
            persist=False,
        )
        completed_run = run.model_copy(
            update={
                "status": "completed",
                "claude_session_id": session_id,
                "finished_at": now_iso(),
            }
        )
        cast(Any, repo).finalize_reply(
            assistant_message=assistant_message,
            updated_thread=thread,
            completed_run=completed_run,
        )
        yield _json_line(
            {
                "type": "done",
                "message": assistant_message.model_dump(mode="json"),
                "session_id": session_id,
                "snapshot_id": evidence_bundle.id,
                "run_id": completed_run.id,
            }
        )
    except Exception as exc:
        if run is not None:
            with suppress(Exception):
                repo.save_run(
                    run.model_copy(
                        update={
                            "status": "failed",
                            "stderr_path": str(exc),
                            "finished_at": now_iso(),
                        }
                    )
                )
        payload: dict[str, object] = {"type": "error", "message": str(exc)}
        if run is not None:
            payload["run_id"] = run.id
        yield _json_line(payload)
        return
