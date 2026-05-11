"""Assistant evidence-bundle construction for retrieval-first orchestration."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import NamedTuple

from app.domains.assistant.application.retrieval import (
    retrieve_experiment_review,
    retrieve_open_ended_coaching,
    retrieve_recovery_briefing,
    retrieve_routine_adherence,
)
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantIntent,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.domains.assistant.dependencies import AssistantReadModelStore, AssistantRecallStore

_MAX_MEMORY_RECORDS = 5
_MAX_PRIOR_BUNDLES = 3
_EXPLICIT_RECALL_SIGNAL = "explicit_recall_language"
_ALLOWED_PRIOR_INTENTS: dict[AssistantIntent, frozenset[AssistantIntent]] = {
    "experiment_review": frozenset({"experiment_review"}),
    "recovery_briefing": frozenset({"recovery_briefing", "open_ended_coaching"}),
    "routine_adherence": frozenset({"routine_adherence", "open_ended_coaching"}),
    "open_ended_coaching": frozenset(
        {"open_ended_coaching", "recovery_briefing", "routine_adherence"}
    ),
}
class _PriorBundleCandidate(NamedTuple):
    priority: int
    created_at: str
    updated_at: str
    bundle_id: str
    bundle: AssistantEvidenceBundle
    match_type: str
    matched_entity_ids: list[str]


def build_evidence_bundle(
    *,
    read_store: AssistantReadModelStore,
    recall_store: AssistantRecallStore,
    route: AssistantRouteDecision,
    entities: Sequence[AssistantResolvedEntity],
    thread_id: str,
    user_message_id: str,
) -> AssistantEvidenceBundle:
    """Build a compact deterministic evidence bundle for a user message."""

    items: list[AssistantEvidenceItem] = []
    gaps: list[str] = []

    if route.intent == "experiment_review":
        route_items, route_gaps = retrieve_experiment_review(
            store=read_store,
            route=route,
            entities=entities,
        )
    elif route.intent == "recovery_briefing":
        route_items, route_gaps = retrieve_recovery_briefing(store=read_store)
    elif route.intent == "routine_adherence":
        route_items, route_gaps = retrieve_routine_adherence(store=read_store)
    elif route.intent == "open_ended_coaching":
        route_items, route_gaps = retrieve_open_ended_coaching(store=read_store)
    else:
        route_items, route_gaps = [], [f"unsupported_intent:{route.intent}"]

    items.extend(route_items)
    gaps.extend(route_gaps)

    items.extend(
        _build_prior_evidence_items(
            store=recall_store,
            route=route,
            current_entities=entities,
            current_thread_id=thread_id,
            last_n=_MAX_PRIOR_BUNDLES,
        )
    )
    items.extend(_build_memory_items(store=recall_store, last_n=_MAX_MEMORY_RECORDS))

    return AssistantEvidenceBundle(
        id=_deterministic_bundle_id(
            intent=route.intent,
            thread_id=thread_id,
            user_message_id=user_message_id,
        ),
        thread_id=thread_id,
        user_message_id=user_message_id,
        intent=route.intent,
        entities=list(entities),
        items=items,
        gaps=list(dict.fromkeys(gaps)),
    )


def _build_prior_evidence_items(
    *,
    store: AssistantRecallStore,
    route: AssistantRouteDecision,
    current_entities: Sequence[AssistantResolvedEntity],
    current_thread_id: str,
    last_n: int,
) -> list[AssistantEvidenceItem]:
    all_bundles = store.list_evidence_bundles(last_n=50)
    other_thread_bundles = [
        bundle for bundle in all_bundles if bundle.thread_id != current_thread_id
    ]
    if not other_thread_bundles:
        return []

    explicit_recall = _EXPLICIT_RECALL_SIGNAL in route.matched_signals
    current_entity_ids = {entity.entity_id for entity in current_entities}
    prior_bundle_candidates: list[_PriorBundleCandidate] = []
    for bundle in other_thread_bundles:
        bundle_entity_ids = _bundle_entity_ids(bundle)
        matched_entity_ids = sorted(current_entity_ids.intersection(bundle_entity_ids))
        match_type: str | None = None
        priority = 0
        if matched_entity_ids:
            match_type = "entity_overlap"
            priority = 3
        elif bundle.intent in _ALLOWED_PRIOR_INTENTS[route.intent]:
            match_type = "intent_family"
            priority = 2
        elif explicit_recall:
            match_type = "explicit_recall"
            priority = 1

        if match_type is None:
            continue
        prior_bundle_candidates.append(
            _PriorBundleCandidate(
                priority=priority,
                created_at=bundle.created_at or "",
                updated_at=bundle.updated_at or "",
                bundle_id=bundle.id,
                bundle=bundle,
                match_type=match_type,
                matched_entity_ids=matched_entity_ids,
            )
        )

    ordered_bundles = sorted(
        prior_bundle_candidates,
        key=lambda c: (c.priority, c.created_at, c.updated_at, c.bundle_id),
        reverse=True,
    )[:last_n]

    items: list[AssistantEvidenceItem] = []
    for candidate in ordered_bundles:
        bundle, match_type, matched_entity_ids = (
            candidate.bundle,
            candidate.match_type,
            candidate.matched_entity_ids,
        )
        items.append(
            AssistantEvidenceItem(
                kind="prior_evidence",
                source="conversation_store.evidence_bundles",
                entity_id=matched_entity_ids[0] if matched_entity_ids else None,
                payload_json={
                    "bundle_id": bundle.id,
                    "thread_id": bundle.thread_id,
                    "intent": bundle.intent,
                    "item_kinds": [item.kind for item in bundle.items],
                    "gaps": list(bundle.gaps),
                    "match_type": match_type,
                    "matched_entity_ids": list(matched_entity_ids),
                    "bundle_entity_ids": _bundle_entity_ids(bundle),
                },
            )
        )
    return items


def _build_memory_items(
    *,
    store: AssistantRecallStore,
    last_n: int,
) -> list[AssistantEvidenceItem]:
    records = sorted(
        store.list_memory_records(last_n=last_n),
        key=lambda record: (
            record.created_at or "",
            record.updated_at or "",
            record.id,
        ),
    )
    return [_memory_item(record) for record in records]


def _memory_item(record: AssistantMemoryRecord) -> AssistantEvidenceItem:
    return AssistantEvidenceItem(
        kind="memory",
        source="conversation_store.memory_records",
        entity_id=record.entity_id,
        payload_json={
            "memory_id": record.id,
            "memory_kind": record.kind,
            "alias_text": record.alias_text,
            "payload_json": dict(record.payload_json),
        },
    )


def _bundle_entity_ids(bundle: AssistantEvidenceBundle) -> list[str]:
    return [entity.entity_id for entity in bundle.entities]


def _deterministic_bundle_id(*, intent: str, thread_id: str, user_message_id: str) -> str:
    raw = f"{thread_id}\x1f{user_message_id}\x1f{intent}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:20]
    return f"evidence-{digest}"

