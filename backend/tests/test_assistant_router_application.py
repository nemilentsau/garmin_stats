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


def test_router_classifies_plural_experiment_scan_questions() -> None:
    decision = route_user_query("Scan my experiments and tell me what is worth continuing.")

    assert decision.intent == "experiment_review"
    assert "plural_experiment_context" in decision.matched_signals


def test_router_marks_shipped_experiment_scan_prompt_as_scan_context() -> None:
    decision = route_user_query(
        "Look at my active routines and experiments. "
        "Tell me what seems worth continuing, what looks noisy, and what needs cleaner tracking."
    )

    assert decision.intent == "experiment_review"
    assert "experiment_routine_scan" in decision.matched_signals


def test_router_classifies_weekly_review_questions_as_open_ended_coaching() -> None:
    query = (
        "Review the recent week and tell me what patterns stand out, "
        "what confounders matter, and what I should adjust next."
    )
    decision = route_user_query(query)

    assert decision.intent == "open_ended_coaching"


def test_router_marks_explicit_recall_language_signal() -> None:
    decision = route_user_query(
        "What did we discuss earlier about my meditation experiment?"
    )

    assert decision.intent == "experiment_review"
    assert "explicit_recall_language" in decision.matched_signals
