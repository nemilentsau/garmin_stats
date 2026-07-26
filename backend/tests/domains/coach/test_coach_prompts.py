"""Tests for stable Coach prompt policy and artifact-reference grammar."""

from app.domains.coach.application.prompts import chat_prompt, review_prompt


def test_review_prompt_defines_durable_artifact_reference_values() -> None:
    prompt = review_prompt("review_run")

    assert "Refs are durable identifiers, never workspace paths or anchors" in prompt
    assert "run: the run id" in prompt
    assert "plot: the image basename only" in prompt
    assert "review: the persisted review id" in prompt
    assert "date: the ISO date" in prompt
    assert "Do not cite plan.md or recovery.md as review refs" in prompt


def test_correction_prompt_requires_a_complete_review_snapshot() -> None:
    prompt = chat_prompt(resumed=False, review_linked=True, revision_requested=True)

    for field in (
        "content_md",
        "outcome",
        "confidence",
        "refs",
        "follow_up_questions",
        "plot_observations",
        "history_used",
        "measurement_assessment",
    ):
        assert field in prompt
    assert "complete replacement" in prompt
