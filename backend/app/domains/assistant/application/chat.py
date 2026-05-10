"""Retrieval-first assistant chat orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel

from app.domains.assistant.application.entity_resolution import resolve_entities
from app.domains.assistant.application.evidence import build_evidence_bundle
from app.domains.assistant.application.router import route_user_query
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantMessageCreateRequest,
    AssistantResolvedEntity,
    AssistantRouteDecision,
    AssistantRun,
)
from app.domains.assistant.dependencies import (
    AssistantConversationStore,
    AssistantReadModelStore,
    AssistantRetrievalStore,
    AssistantRuntime,
)
from app.utils.timeutil import now_iso

_LOWERCASE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_MAX_MEMORY_RECORDS = 5
_MAX_ALIAS_PHRASE_TOKENS = 6
_QUESTION_WORDS = {
    "are",
    "can",
    "could",
    "did",
    "do",
    "does",
    "had",
    "has",
    "have",
    "how",
    "is",
    "may",
    "might",
    "should",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "would",
}
_MIN_ALIAS_TOKENS = 2
_MAX_ALIAS_TOKENS = 6
_MIN_ALIAS_SCORE = 0.9


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
        alias_candidates: tuple[str, ...] | None = None,
    ):
        return self._conversation_store.list_memory_records(
            kind=kind,
            last_n=last_n,
            alias_candidates=alias_candidates,
        )

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
        return f"Grounded quick read: {experiment_name} is loaded from current experiment evidence."
    day_label = "day" if exposure_count == 1 else "days"
    return (
        f"Grounded quick read: {experiment_name} has "
        f"{exposure_count} logged exposure {day_label}."
    )


def _build_entity_alias_memory_record(
    *,
    route: AssistantRouteDecision,
    entities: list[AssistantResolvedEntity],
    memory_records: list[AssistantMemoryRecord],
    query: str,
) -> AssistantMemoryRecord | None:
    if route.intent != "experiment_review":
        return None

    experiment_entities = [entity for entity in entities if entity.kind == "experiment"]
    if len(experiment_entities) != 1:
        return None

    entity = experiment_entities[0]
    if entity.score < _MIN_ALIAS_SCORE:
        return None

    alias_text = query.strip()
    if not alias_text:
        return None

    alias_tokens = _LOWERCASE_TOKEN_PATTERN.findall(alias_text.lower())
    if not (_MIN_ALIAS_TOKENS <= len(alias_tokens) <= _MAX_ALIAS_TOKENS):
        return None
    if any(token in _QUESTION_WORDS for token in alias_tokens):
        return None

    normalized_alias = " ".join(alias_tokens)
    existing_aliases = {
        " ".join(_LOWERCASE_TOKEN_PATTERN.findall(record.alias_text.lower()))
        for record in memory_records
        if record.kind == "entity_alias"
        and record.entity_id == entity.entity_id
        and record.alias_text
    }
    if normalized_alias in existing_aliases:
        return None

    return AssistantMemoryRecord(
        id=f"memory-{uuid4().hex}",
        kind="entity_alias",
        entity_id=entity.entity_id,
        alias_text=alias_text,
        payload_json={
            "source_query": query,
            "resolved_entity_label": entity.label,
            "resolved_entity_score": entity.score,
            "route_intent": route.intent,
        },
        created_at=now_iso(),
    )


def _maybe_reroute_from_memory_alias(
    *,
    memory_records: list[AssistantMemoryRecord],
    route: AssistantRouteDecision,
    read_store: AssistantReadModelStore,
    query: str,
) -> tuple[AssistantRouteDecision, list[AssistantResolvedEntity]]:
    if route.intent == "experiment_review":
        return route, []
    if not _matches_saved_entity_alias(memory_records=memory_records, query=query):
        return route, []

    experiment_route = AssistantRouteDecision(
        intent="experiment_review",
        confidence=route.confidence,
        matched_signals=[*route.matched_signals, "memory_alias_reroute"],
    )
    entities = resolve_entities(
        store=read_store,
        memory=memory_records,
        route=experiment_route,
        query=query,
    )
    if not entities:
        return route, []

    matched_entity_ids = {entity.entity_id for entity in entities if entity.kind == "experiment"}
    if not _matches_saved_entity_alias(
        memory_records=memory_records,
        query=query,
        entity_ids=matched_entity_ids,
    ):
        return route, []
    return experiment_route, entities


def _matches_saved_entity_alias(
    *,
    memory_records: list[AssistantMemoryRecord],
    query: str,
    entity_ids: set[str] | None = None,
) -> bool:
    query_tokens = _alias_tokens(query)
    if not query_tokens:
        return False

    for record in memory_records:
        if record.kind != "entity_alias" or not record.alias_text or not record.entity_id:
            continue
        if entity_ids is not None and record.entity_id not in entity_ids:
            continue
        if _query_contains_alias(
            query_tokens=query_tokens,
            alias_tokens=_alias_tokens(record.alias_text),
        ):
            return True
    return False


def _alias_tokens(value: str) -> list[str]:
    return _LOWERCASE_TOKEN_PATTERN.findall(value.lower())


def _query_contains_alias(*, query_tokens: list[str], alias_tokens: list[str]) -> bool:
    if not alias_tokens or len(alias_tokens) > len(query_tokens):
        return False
    window_size = len(alias_tokens)
    for index in range(len(query_tokens) - window_size + 1):
        if query_tokens[index : index + window_size] == alias_tokens:
            return True
    return False


def _resolution_memory_records(
    repo: AssistantConversationStore,
    *,
    query: str,
) -> tuple[list[AssistantMemoryRecord], list[AssistantMemoryRecord]]:
    prompt_memory_records = list(repo.list_memory_records(last_n=_MAX_MEMORY_RECORDS))
    alias_candidates = _alias_query_candidates(query)
    alias_memory_records = list(
        repo.list_memory_records(
            kind="entity_alias",
            alias_candidates=alias_candidates or None,
        )
    )

    merged_by_id: dict[str, AssistantMemoryRecord] = {
        record.id: record for record in prompt_memory_records
    }
    for record in alias_memory_records:
        merged_by_id.setdefault(record.id, record)

    return prompt_memory_records, list(merged_by_id.values())


def _alias_query_candidates(query: str) -> tuple[str, ...]:
    query_tokens = _alias_tokens(query)
    if not query_tokens:
        return ()

    max_window = min(len(query_tokens), _MAX_ALIAS_PHRASE_TOKENS)
    candidates: dict[str, None] = {}
    for window_size in range(1, max_window + 1):
        for index in range(len(query_tokens) - window_size + 1):
            candidate = " ".join(query_tokens[index : index + window_size])
            candidates.setdefault(candidate, None)
    return tuple(candidates.keys())


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
    pending_memory_record: AssistantMemoryRecord | None = None

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

        prompt_memory_records, resolution_memory_records = _resolution_memory_records(
            repo,
            query=request.content,
        )
        route = route_user_query(request.content)
        entities = resolve_entities(
            store=read_store,
            memory=resolution_memory_records,
            route=route,
            query=request.content,
        )
        if not entities:
            route, rerouted_entities = _maybe_reroute_from_memory_alias(
                memory_records=resolution_memory_records,
                route=route,
                read_store=read_store,
                query=request.content,
            )
            if rerouted_entities:
                entities = rerouted_entities
        pending_memory_record = _build_entity_alias_memory_record(
            route=route,
            entities=entities,
            memory_records=resolution_memory_records,
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
