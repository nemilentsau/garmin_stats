"""Prepare deterministic retrieval context for one assistant chat turn.

This module owns the side-effect-free portion of chat setup: memory lookup,
intent routing, entity resolution, pending alias-memory decisions, and evidence
bundle assembly. The caller remains responsible for user-message persistence,
run lifecycle writes, and final reply persistence.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.assistant.application.entity_resolution import resolve_entities
from app.domains.assistant.application.evidence import build_evidence_bundle
from app.domains.assistant.application.intent_routing import route_user_query
from app.domains.assistant.application.memory_aliases import (
    build_entity_alias_memory_record,
    confirm_alias_reroute,
    load_resolution_memory_records,
    maybe_reroute_from_memory_alias,
)
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantRouteDecision,
)
from app.domains.assistant.dependencies import (
    AssistantReadModelStore,
    AssistantRecallStore,
)


@dataclass(frozen=True)
class PreparedTurnContext:
    """Deterministic context needed before the runtime can answer."""

    route: AssistantRouteDecision
    evidence_bundle: AssistantEvidenceBundle
    prompt_memory_records: list[AssistantMemoryRecord]
    pending_memory_record: AssistantMemoryRecord | None


def prepare_turn_context(
    *,
    recall_store: AssistantRecallStore,
    read_store: AssistantReadModelStore,
    thread_id: str,
    user_message_id: str,
    query: str,
) -> PreparedTurnContext:
    """Return route, memory, entity, and evidence context for one user query.

    Any returned `pending_memory_record` must be saved by the caller only when
    the reply completes; this helper never writes it itself.
    """
    prompt_memory_records, entity_memory_records = load_resolution_memory_records(
        recall_store,
        query=query,
    )
    route = route_user_query(query)
    original_route = route
    route, alias_entity_ids = maybe_reroute_from_memory_alias(
        memory_records=entity_memory_records,
        route=route,
        query=query,
    )
    entities = resolve_entities(
        store=read_store,
        memory=entity_memory_records,
        route=route,
        query=query,
    )
    route, entities = confirm_alias_reroute(
        route=route,
        original_route=original_route,
        entities=entities,
        alias_entity_ids=alias_entity_ids,
    )

    pending_memory_record = build_entity_alias_memory_record(
        route=route,
        entities=entities,
        memory_records=entity_memory_records,
        query=query,
    )
    evidence_bundle = build_evidence_bundle(
        read_store=read_store,
        recall_store=recall_store,
        route=route,
        entities=entities,
        thread_id=thread_id,
        user_message_id=user_message_id,
    )
    return PreparedTurnContext(
        route=route,
        evidence_bundle=evidence_bundle,
        prompt_memory_records=prompt_memory_records,
        pending_memory_record=pending_memory_record,
    )
