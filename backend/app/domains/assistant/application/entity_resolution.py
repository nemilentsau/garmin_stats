"""Deterministic entity resolution for retrieval-first assistant routes."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from app.domains.assistant.application.ports import AssistantReadModelStore
from app.domains.assistant.application.types import (
    EXPERIMENT_REVIEW_TERMS,
    LOWERCASE_TOKEN_PATTERN,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.models import Experiment

_ID_SEGMENT_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "does",
    "far",
    "how",
    "like",
    "look",
    "our",
    "so",
    "the",
}
_MIN_EXPERIMENT_MATCH_SCORE = 0.35
_AMBIGUITY_MARGIN = 0.12


def resolve_entities(
    *,
    store: AssistantReadModelStore,
    memory: Sequence[AssistantMemoryRecord],
    route: AssistantRouteDecision,
    query: str,
) -> list[AssistantResolvedEntity]:
    if route.intent != "experiment_review":
        return []
    return _resolve_experiment_entities(store=store, memory=memory, query=query)


def _resolve_experiment_entities(
    *,
    store: AssistantReadModelStore,
    memory: Sequence[AssistantMemoryRecord],
    query: str,
) -> list[AssistantResolvedEntity]:
    candidate_experiments = store.list_experiments(statuses=("active", "draft"))
    if not candidate_experiments:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    alias_tokens = _alias_tokens_by_entity(memory)
    scored_candidates: list[tuple[Experiment, float]] = []
    lowered_query = query.lower()
    for experiment in candidate_experiments:
        score = _experiment_match_score(
            query_tokens=query_tokens,
            query_text=lowered_query,
            experiment=experiment,
            alias_tokens=alias_tokens.get(experiment.id, []),
        )
        if score > 0.0:
            scored_candidates.append((experiment, score))

    if not scored_candidates:
        return []

    scored_candidates.sort(key=lambda item: item[1], reverse=True)
    best_experiment, best_score = scored_candidates[0]
    second_score = scored_candidates[1][1] if len(scored_candidates) > 1 else 0.0
    if best_score < _MIN_EXPERIMENT_MATCH_SCORE:
        return []
    if (best_score - second_score) < _AMBIGUITY_MARGIN:
        return []

    return [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id=best_experiment.id,
            label=best_experiment.name,
            score=round(_bounded_confidence(best_score), 3),
        )
    ]


def _experiment_match_score(
    *,
    query_tokens: set[str],
    query_text: str,
    experiment: Experiment,
    alias_tokens: Sequence[set[str]],
) -> float:
    name_tokens = _tokenize(experiment.name)
    if not name_tokens:
        return 0.0

    score = _overlap_score(query_tokens, name_tokens)
    if _query_mentions_experiment_id(query_text, experiment.id):
        score += 0.40

    if alias_tokens:
        score = max(score, max(_overlap_score(query_tokens, alias) for alias in alias_tokens))

    if query_tokens.intersection(EXPERIMENT_REVIEW_TERMS):
        score += 0.08

    return score


def _query_mentions_experiment_id(query_text: str, experiment_id: str) -> bool:
    normalized_id = _normalize_id(experiment_id)
    if not normalized_id:
        return False
    for segment in _ID_SEGMENT_PATTERN.findall(query_text.lower()):
        if _normalize_id(segment) == normalized_id:
            return True
    return False


def _normalize_id(value: str) -> str:
    parts = LOWERCASE_TOKEN_PATTERN.findall(value.lower())
    return "-".join(parts)


def _alias_tokens_by_entity(memory: Sequence[AssistantMemoryRecord]) -> dict[str, list[set[str]]]:
    entity_alias_tokens: dict[str, list[set[str]]] = defaultdict(list)
    for record in memory:
        if record.kind != "entity_alias":
            continue
        if not record.entity_id or not record.alias_text:
            continue
        tokens = _tokenize(record.alias_text)
        if tokens:
            entity_alias_tokens[record.entity_id].append(tokens)
    return entity_alias_tokens


def _overlap_score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = query_tokens.intersection(candidate_tokens)
    if not overlap:
        return 0.0
    return len(overlap) / len(candidate_tokens)


def _bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in LOWERCASE_TOKEN_PATTERN.findall(text.lower())
        if token and token not in _STOP_WORDS
    }
