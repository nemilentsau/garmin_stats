"""Deterministic intent router for retrieval-first assistant queries."""

from __future__ import annotations

import re

from app.domains.assistant.application.types import AssistantIntent, AssistantRouteDecision

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_INTENT_ORDER: tuple[AssistantIntent, ...] = (
    "experiment_review",
    "recovery_briefing",
    "routine_adherence",
    "open_ended_coaching",
)


def route_user_query(query: str) -> AssistantRouteDecision:
    text = query.lower()
    tokens = set(_TOKEN_PATTERN.findall(text))
    scores = {intent: 0.0 for intent in _INTENT_ORDER}
    signals = {intent: [] for intent in _INTENT_ORDER}

    def add_signal(intent: AssistantIntent, weight: float, signal: str) -> None:
        scores[intent] += weight
        signals[intent].append(signal)

    if tokens.intersection({"experiment", "trial", "study"}):
        add_signal("experiment_review", 0.55, "mentions_experiment")
    if any(phrase in text for phrase in ("so far", "look like", "results", "effect")):
        add_signal("experiment_review", 0.25, "review_phrase")
    if tokens.intersection({"meditation", "intervention", "protocol"}):
        add_signal("experiment_review", 0.15, "intervention_keyword")
    if "how" in tokens and "experiment" in tokens:
        add_signal("experiment_review", 0.10, "how_experiment_question")

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

    ranked = sorted(
        _INTENT_ORDER,
        key=lambda intent: (scores[intent], -_INTENT_ORDER.index(intent)),
        reverse=True,
    )
    top_intent = ranked[0]
    top_score = min(scores[top_intent], 0.99)
    second_score = scores[ranked[1]] if len(ranked) > 1 else 0.0

    if top_score <= 0.0:
        return AssistantRouteDecision(
            intent="open_ended_coaching",
            confidence=0.50,
            matched_signals=[],
        )

    margin_penalty = max(0.0, 0.20 - (top_score - second_score))
    confidence = max(0.50, min(0.99, top_score - margin_penalty))
    return AssistantRouteDecision(
        intent=top_intent,
        confidence=round(confidence, 3),
        matched_signals=signals[top_intent],
    )
