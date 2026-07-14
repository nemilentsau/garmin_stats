"""Tests for stable Coach prompt policy and artifact-reference grammar."""

from app.domains.coach.application.prompts import review_prompt


def test_review_prompt_defines_durable_artifact_reference_values() -> None:
    prompt = review_prompt("review_run")

    assert "Refs are durable identifiers, never workspace paths or anchors" in prompt
    assert "run: the run id" in prompt
    assert "plot: the image basename only" in prompt
    assert "review: the persisted review id" in prompt
    assert "date: the ISO date" in prompt
    assert "Do not cite plan.md or recovery.md as review refs" in prompt
