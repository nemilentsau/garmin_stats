"""Assistant memory-alias policy for chat orchestration.

This module owns short alias recall for experiment review conversations: it
loads prompt and lookup memory, reroutes saved aliases into experiment review
when appropriate, and decides when a new alias memory should be persisted. Chat
orchestration supplies stores and route decisions, while this module owns the
alias matching thresholds and token-window policy.
"""

from __future__ import annotations

from uuid import uuid4

from app.domains.assistant.application.entity_resolution import resolve_entities
from app.domains.assistant.contracts import (
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.domains.assistant.dependencies import (
    AssistantConversationStore,
    AssistantReadModelStore,
)
from app.domains.assistant.domain.text import normalize_alias, tokenize
from app.utils.timeutil import now_iso

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


def load_resolution_memory_records(
    repo: AssistantConversationStore,
    *,
    query: str,
) -> tuple[list[AssistantMemoryRecord], list[AssistantMemoryRecord]]:
    """Load prompt memory plus alias lookup memory for entity resolution.

    Prompt memory remains capped for runtime context. Alias lookup expands that
    set using query token windows so saved aliases outside the prompt window can
    still resolve a user follow-up.
    """
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


def maybe_reroute_from_memory_alias(
    *,
    memory_records: list[AssistantMemoryRecord],
    route: AssistantRouteDecision,
    read_store: AssistantReadModelStore,
    query: str,
) -> tuple[AssistantRouteDecision, list[AssistantResolvedEntity]]:
    """Promote a non-experiment route when the query matches a saved alias."""
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


def build_entity_alias_memory_record(
    *,
    route: AssistantRouteDecision,
    entities: list[AssistantResolvedEntity],
    memory_records: list[AssistantMemoryRecord],
    query: str,
) -> AssistantMemoryRecord | None:
    """Return a new alias memory when a short query confidently names one experiment."""
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

    alias_tokens = tokenize(alias_text)
    if not (_MIN_ALIAS_TOKENS <= len(alias_tokens) <= _MAX_ALIAS_TOKENS):
        return None
    if any(token in _QUESTION_WORDS for token in alias_tokens):
        return None

    normalized_alias = " ".join(alias_tokens)
    existing_aliases = {
        normalize_alias(record.alias_text)
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


def _matches_saved_entity_alias(
    *,
    memory_records: list[AssistantMemoryRecord],
    query: str,
    entity_ids: set[str] | None = None,
) -> bool:
    query_tokens = tokenize(query)
    if not query_tokens:
        return False

    for record in memory_records:
        if record.kind != "entity_alias" or not record.alias_text or not record.entity_id:
            continue
        if entity_ids is not None and record.entity_id not in entity_ids:
            continue
        if _query_contains_alias(
            query_tokens=query_tokens,
            alias_tokens=tokenize(record.alias_text),
        ):
            return True
    return False


def _query_contains_alias(*, query_tokens: list[str], alias_tokens: list[str]) -> bool:
    if not alias_tokens or len(alias_tokens) > len(query_tokens):
        return False
    window_size = len(alias_tokens)
    for index in range(len(query_tokens) - window_size + 1):
        if query_tokens[index : index + window_size] == alias_tokens:
            return True
    return False


def _alias_query_candidates(query: str) -> tuple[str, ...]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return ()

    max_window = min(len(query_tokens), _MAX_ALIAS_PHRASE_TOKENS)
    candidates: dict[str, None] = {}
    for window_size in range(1, max_window + 1):
        for index in range(len(query_tokens) - window_size + 1):
            candidate = " ".join(query_tokens[index : index + window_size])
            candidates.setdefault(candidate, None)
    return tuple(candidates.keys())
