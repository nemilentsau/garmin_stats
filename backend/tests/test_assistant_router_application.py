"""Tests for deterministic assistant query routing."""

from app.domains.assistant.application.router import route_user_query


def test_router_classifies_experiment_review_questions() -> None:
    decision = route_user_query("How does our meditation experiment look like so far?")

    assert decision.intent == "experiment_review"
    assert decision.confidence >= 0.9


def test_router_classifies_recovery_briefing_questions() -> None:
    decision = route_user_query("Give me a quick recovery briefing for today")

    assert decision.intent == "recovery_briefing"


def test_router_classifies_routine_adherence_questions() -> None:
    decision = route_user_query("Did I stick to my routine this week?")

    assert decision.intent == "routine_adherence"


def test_router_classifies_trial_questions_as_experiment_review() -> None:
    decision = route_user_query("How is the meditation trial going?")

    assert decision.intent == "experiment_review"
