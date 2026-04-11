"""Assistant evidence-bundle construction for retrieval-first orchestration."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.domains.assistant.application.ports import AssistantRetrievalStore
from app.domains.assistant.application.retrieval import retrieve_experiment_review
from app.domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)

_MAX_PRIOR_BUNDLES = 3
_MAX_MEMORY_RECORDS = 5
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


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
        route_items, route_gaps = retrieve_experiment_review(store=store, entities=entities)
        items.extend(route_items)
        gaps.extend(route_gaps)
    else:
        gaps.append(f"unsupported_intent:{route.intent}")

    items.extend(
        _build_prior_evidence_items(
            store=store,
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
    current_thread_id: str,
    last_n: int,
) -> list[AssistantEvidenceItem]:
    bundles = store.list_evidence_bundles(last_n=last_n * 3)
    other_thread_bundles = [bundle for bundle in bundles if bundle.thread_id != current_thread_id]
    if not other_thread_bundles:
        return []

    ordered_bundles = sorted(
        other_thread_bundles,
        key=lambda bundle: (
            bundle.created_at or "",
            bundle.updated_at or "",
            bundle.id,
        ),
    )[-last_n:]

    items: list[AssistantEvidenceItem] = []
    for bundle in ordered_bundles:
        items.append(
            AssistantEvidenceItem(
                kind="prior_evidence",
                source="conversation_store.evidence_bundles",
                entity_id=_first_experiment_entity_id(bundle.entities),
                payload_json={
                    "bundle_id": bundle.id,
                    "thread_id": bundle.thread_id,
                    "intent": bundle.intent,
                    "item_kinds": [item.kind for item in bundle.items],
                    "gaps": list(bundle.gaps),
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


def _first_experiment_entity_id(entities: Sequence[AssistantResolvedEntity]) -> str | None:
    for entity in entities:
        if entity.kind == "experiment":
            return entity.entity_id
    return None


def _deterministic_bundle_id(*, intent: str, thread_id: str, user_message_id: str) -> str:
    return f"evidence-{_slug(thread_id)}-{_slug(user_message_id)}-{_slug(intent)}"


def _slug(value: str) -> str:
    normalized = _SLUG_PATTERN.sub("-", value.strip().lower()).strip("-")
    return normalized or "unknown"


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
