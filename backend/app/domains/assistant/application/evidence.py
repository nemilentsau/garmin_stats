"""Assistant evidence-bundle construction for retrieval-first orchestration."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.domains.assistant.application.ports import AssistantRetrievalStore
from app.domains.assistant.application.retrieval import (
    retrieve_experiment_review,
    retrieve_open_ended_coaching,
    retrieve_recovery_briefing,
    retrieve_routine_adherence,
)
from app.domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantIntent,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)

_MAX_PRIOR_BUNDLES = 3
_MAX_MEMORY_RECORDS = 5
_EXPLICIT_RECALL_SIGNAL = "explicit_recall_language"
_ALLOWED_PRIOR_INTENTS: dict[AssistantIntent, frozenset[AssistantIntent]] = {
    "experiment_review": frozenset({"experiment_review"}),
    "recovery_briefing": frozenset({"recovery_briefing", "open_ended_coaching"}),
    "routine_adherence": frozenset({"routine_adherence", "open_ended_coaching"}),
    "open_ended_coaching": frozenset(
        {"open_ended_coaching", "recovery_briefing", "routine_adherence"}
    ),
}
_PriorBundleCandidate = tuple[
    int,
    str,
    str,
    str,
    AssistantEvidenceBundle,
    str,
    list[str],
]


def build_evidence_bundle(
    *,
    store: AssistantRetrievalStore,
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
            store=store,
            route=route,
            entities=entities,
        )
    elif route.intent == "recovery_briefing":
        route_items, route_gaps = retrieve_recovery_briefing(store=store)
    elif route.intent == "routine_adherence":
        route_items, route_gaps = retrieve_routine_adherence(store=store)
    elif route.intent == "open_ended_coaching":
        route_items, route_gaps = retrieve_open_ended_coaching(store=store)
    else:
        route_items, route_gaps = [], [f"unsupported_intent:{route.intent}"]

    items.extend(route_items)
    gaps.extend(route_gaps)

    items.extend(
        _build_prior_evidence_items(
            store=store,
            route=route,
            current_entities=entities,
            current_thread_id=thread_id,
            last_n=_MAX_PRIOR_BUNDLES,
        )
    )
    items.extend(_build_memory_items(store=store, last_n=_MAX_MEMORY_RECORDS))

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
        gaps=_dedupe(gaps),
    )


def _build_prior_evidence_items(
    *,
    store: AssistantRetrievalStore,
    route: AssistantRouteDecision,
    current_entities: Sequence[AssistantResolvedEntity],
    current_thread_id: str,
    last_n: int,
) -> list[AssistantEvidenceItem]:
    all_bundles = store.list_evidence_bundles()
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
            (
                priority,
                bundle.created_at or "",
                bundle.updated_at or "",
                bundle.id,
                bundle,
                match_type,
                matched_entity_ids,
            )
        )

    ordered_bundles = sorted(
        prior_bundle_candidates,
        key=lambda candidate: (
            candidate[0],
            candidate[1],
            candidate[2],
            candidate[3],
        ),
        reverse=True,
    )[:last_n]

    items: list[AssistantEvidenceItem] = []
    for _, _, _, _, bundle, match_type, matched_entity_ids in ordered_bundles:
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
    store: AssistantRetrievalStore,
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


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
