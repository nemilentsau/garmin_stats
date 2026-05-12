"""Retrieval-first assistant chat orchestration."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from uuid import uuid4

from app.domains.assistant.application.entity_resolution import resolve_entities
from app.domains.assistant.application.evidence import build_evidence_bundle
from app.domains.assistant.application.intent_routing import route_user_query
from app.domains.assistant.application.memory_aliases import (
    build_entity_alias_memory_record,
    load_resolution_memory_records,
    maybe_reroute_from_memory_alias,
)
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantMessageCreateRequest,
    AssistantRun,
    AssistantThread,
)
from app.domains.assistant.dependencies import (
    AssistantConversationStore,
    AssistantReadModelStore,
    AssistantRuntime,
)
from app.utils.timeutil import now_iso


def _json_line(payload: dict[str, object]) -> str:
    return json.dumps(payload) + "\n"


def _model_for_thread(thread: AssistantThread) -> str:
    return thread.model or "sonnet"


def _thread_with_state(
    *,
    thread: AssistantThread,
    last_message_at: str,
    snapshot_id: str | None = None,
    session_id: str | None = None,
) -> AssistantThread:
    updates: dict[str, object] = {"last_message_at": last_message_at}
    if snapshot_id is not None:
        updates["last_context_snapshot_id"] = snapshot_id
    if session_id is not None:
        updates["claude_session_id"] = session_id
    return thread.model_copy(update=updates)


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


async def stream_reply(
    *,
    repo: AssistantConversationStore,
    read_store: AssistantReadModelStore,
    runtime: AssistantRuntime,
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    run: AssistantRun | None = None
    thread: AssistantThread | None = None
    evidence_bundle: AssistantEvidenceBundle | None = None
    assistant_chunks: list[str] = []
    session_id: str | None = None
    pending_memory_record: AssistantMemoryRecord | None = None

    try:
        thread = repo.get_thread(thread_id)
        if thread is None:
            raise LookupError(f"Assistant thread '{thread_id}' not found")

        prior_messages = repo.list_messages(thread_id)
        user_message = AssistantMessage(
            id=request.id,
            thread_id=thread_id,
            role="user",
            content_markdown=request.content,
            created_at=now_iso(),
        )
        repo.save_message(user_message)

        prompt_memory_records, entity_memory_records = load_resolution_memory_records(
            repo,
            query=request.content,
        )
        route = route_user_query(request.content)
        original_route = route
        route, alias_entity_ids = maybe_reroute_from_memory_alias(
            memory_records=entity_memory_records,
            route=route,
            query=request.content,
        )
        entities = resolve_entities(
            store=read_store,
            memory=entity_memory_records,
            route=route,
            query=request.content,
        )
        if alias_entity_ids:
            # A memory-alias reroute only stands when resolution lands on that alias's entity.
            resolved_experiment_ids = {
                entity.entity_id for entity in entities if entity.kind == "experiment"
            }
            if not resolved_experiment_ids.intersection(alias_entity_ids):
                route = original_route
                entities = []
        pending_memory_record = build_entity_alias_memory_record(
            route=route,
            entities=entities,
            memory_records=entity_memory_records,
            query=request.content,
        )
        evidence_bundle = build_evidence_bundle(
            read_store=read_store,
            recall_store=repo,
            route=route,
            entities=entities,
            thread_id=thread.id,
            user_message_id=request.id,
        )

        run = AssistantRun(
            id=f"run-{uuid4().hex}",
            task_type="chat",
            status="running",
            thread_id=thread.id,
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
            memory_records=prompt_memory_records,
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
        thread = _thread_with_state(
            thread=thread,
            last_message_at=assistant_message.created_at or now_iso(),
            snapshot_id=evidence_bundle.id,
            session_id=session_id,
        )
        completed_run = run.model_copy(
            update={
                "status": "completed",
                "claude_session_id": session_id,
                "finished_at": now_iso(),
            }
        )
        repo.finalize_reply(
            assistant_message=assistant_message,
            updated_thread=thread,
            completed_run=completed_run,
            memory_record=pending_memory_record,
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
                usage_json = dict(run.usage_json)
                usage_json["last_error"] = str(exc)
                repo.save_run(
                    run.model_copy(
                        update={
                            "status": "failed",
                            "stderr_path": None,
                            "usage_json": usage_json,
                            "finished_at": now_iso(),
                        }
                    )
                )
        payload: dict[str, object] = {"type": "error", "message": str(exc)}
        if run is not None:
            payload["run_id"] = run.id
        yield _json_line(payload)
        return
