"""Classify assistant messages before retrieval.

This module owns deterministic intent classification for one user message. It
returns an ``AssistantRouteDecision`` with confidence and matched signals, then
leaves entity resolution, evidence retrieval, and runtime execution to the
neighboring application modules.
"""

from __future__ import annotations

from app.domains.assistant.contracts import (
    AssistantIntent,
    AssistantRouteDecision,
)
from app.domains.assistant.domain.text import tokenize

_EXPERIMENT_REVIEW_TERMS = frozenset({"experiment", "trial", "study"})
_PLURAL_EXPERIMENT_REVIEW_TERMS = frozenset({"experiments", "trials", "studies"})
_ALL_EXPERIMENT_REVIEW_TERMS = (
    _EXPERIMENT_REVIEW_TERMS | _PLURAL_EXPERIMENT_REVIEW_TERMS
)
_RECALL_LANGUAGE_PHRASES = (
    "what did we say",
    "what did we discuss",
    "last thread",
    "previous thread",
    "earlier thread",
    "last conversation",
    "previous conversation",
    "earlier conversation",
)
_INTENT_ORDER: tuple[AssistantIntent, ...] = (
    "experiment_review",
    "recovery_briefing",
    "routine_adherence",
    "open_ended_coaching",
)


def route_user_query(query: str) -> AssistantRouteDecision:
    """Return the retrieval intent and signals inferred from a user query."""

    text = query.lower()
    tokens = set(tokenize(text))
    scores = {intent: 0.0 for intent in _INTENT_ORDER}
    signals = {intent: [] for intent in _INTENT_ORDER}

    def add_signal(intent: AssistantIntent, weight: float, signal: str) -> None:
        scores[intent] += weight
        signals[intent].append(signal)

    if tokens.intersection(_ALL_EXPERIMENT_REVIEW_TERMS):
        add_signal("experiment_review", 0.55, "mentions_experiment")
    if tokens.intersection(_PLURAL_EXPERIMENT_REVIEW_TERMS):
        add_signal("experiment_review", 0.10, "plural_experiment_context")
    if any(phrase in text for phrase in ("so far", "look like", "results", "effect")):
        add_signal("experiment_review", 0.25, "review_phrase")
    if tokens.intersection({"meditation", "intervention", "protocol"}):
        add_signal("experiment_review", 0.15, "intervention_keyword")
    if "how" in tokens and "experiment" in tokens:
        add_signal("experiment_review", 0.10, "how_experiment_question")
    if tokens.intersection({"scan", "scanning"}):
        add_signal("experiment_review", 0.05, "scan_keyword")
    if tokens.intersection(_ALL_EXPERIMENT_REVIEW_TERMS) and tokens.intersection(
        {"routine", "routines", "tracking"}
    ):
        add_signal("experiment_review", 0.10, "experiment_routine_scan")

    if tokens.intersection({"recovery", "readiness"}):
        add_signal("recovery_briefing", 0.60, "mentions_recovery")
    if tokens.intersection({"briefing", "brief", "summary"}):
        add_signal("recovery_briefing", 0.25, "briefing_keyword")
    if tokens.intersection({"today", "morning"}):
        add_signal("recovery_briefing", 0.10, "current_day_context")
    if "quick" in tokens:
        add_signal("recovery_briefing", 0.05, "quick_request")

    if tokens.intersection({"routine", "routines", "habit", "habits"}):
        add_signal("routine_adherence", 0.45, "mentions_routine")
    if tokens.intersection({"adherence", "consistent", "streak", "stick", "followed"}):
        add_signal("routine_adherence", 0.35, "adherence_keyword")
    if tokens.intersection({"missed", "skip", "skipped"}):
        add_signal("routine_adherence", 0.15, "missed_session_keyword")

    if tokens.intersection({"coach", "advice", "suggestion", "suggestions"}):
        add_signal("open_ended_coaching", 0.40, "coaching_keyword")
    if text.startswith(("how can i", "what should i")):
        add_signal("open_ended_coaching", 0.30, "open_question_prefix")
    if tokens.intersection(
        {
            "review",
            "reviews",
            "pattern",
            "patterns",
            "confounder",
            "confounders",
            "adjust",
            "adjustment",
        }
    ):
        add_signal("open_ended_coaching", 0.25, "reflective_review_keyword")
    if tokens.intersection({"week", "weekly", "recent"}):
        add_signal("open_ended_coaching", 0.10, "recent_window_context")

    ranked = sorted(
        _INTENT_ORDER,
        key=lambda intent: (scores[intent], -_INTENT_ORDER.index(intent)),
        reverse=True,
    )
    top_intent = ranked[0]
    top_score = min(scores[top_intent], 0.99)
    second_score = scores[ranked[1]] if len(ranked) > 1 else 0.0

    if top_score <= 0.0:
        matched_signals = []
        if _has_explicit_recall_language(text):
            matched_signals.append("explicit_recall_language")
        return AssistantRouteDecision(
            intent="open_ended_coaching",
            confidence=0.50,
            matched_signals=matched_signals,
        )

    margin_penalty = max(0.0, 0.20 - (top_score - second_score))
    confidence = max(0.50, min(0.99, top_score - margin_penalty))
    matched_signals = list(signals[top_intent])
    if _has_explicit_recall_language(text):
        matched_signals.append("explicit_recall_language")
    return AssistantRouteDecision(
        intent=top_intent,
        confidence=round(confidence, 3),
        matched_signals=matched_signals,
    )


def _has_explicit_recall_language(text: str) -> bool:
    return any(phrase in text for phrase in _RECALL_LANGUAGE_PHRASES)
