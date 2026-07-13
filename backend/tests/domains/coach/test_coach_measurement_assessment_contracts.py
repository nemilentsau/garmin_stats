"""Contract tests for structured coach measurement assessments."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.coach import contracts
from app.domains.coach.contracts import CoachMeasurementAssessment


def _assessment(**updates: object) -> CoachMeasurementAssessment:
    values: dict[str, object] = {
        "run_id": "run-1",
        "occurrence_key": "running:lthr:d08",
        "status": "valid",
        "rationale": "The uninterrupted effort and strap data are credible.",
    }
    values.update(updates)
    return CoachMeasurementAssessment.model_validate(values)


def test_measurement_assessment_accepts_exact_structured_target():
    assessment = _assessment(rationale="x")

    assert assessment.run_id == "run-1"
    assert assessment.occurrence_key == "running:lthr:d08"
    assert assessment.status == "valid"
    assert assessment.rationale == "x"


@pytest.mark.parametrize("rationale", ["", "   \t\n"])
def test_measurement_assessment_rejects_empty_or_whitespace_rationale(rationale: str):
    with pytest.raises(ValidationError):
        _assessment(rationale=rationale)


def test_measurement_assessment_rejects_rationale_over_1000_characters():
    assert len(_assessment(rationale="x" * 1000).rationale) == 1000

    with pytest.raises(ValidationError):
        _assessment(rationale="x" * 1001)


def test_measurement_assessment_rejects_unknown_status_and_extra_fields():
    with pytest.raises(ValidationError):
        _assessment(status="approved")
    with pytest.raises(ValidationError):
        _assessment(confidence="high")


def test_outputs_and_durable_records_accept_absent_assessment_for_compatibility():
    review_output = contracts.ReviewOutput(
        verdict="compliant",
        review_md="Review",
        observations=[],
        concerns=[],
        suggestions=[],
        plan_adjustments=[],
        evidence_limits=[],
        plots_viewed=[],
        refs=[],
        journal_entry_md="Journal",
    )
    chat_output = contracts.ChatOutput(answer_md="Answer", evidence_limits=[], refs=[])
    review = contracts.CoachReview.model_validate(
        {
            "id": "review-1",
            "date": "2026-07-12",
            "kind": "run",
            "run_id": "run-1",
            "occurrence_key": "running:lthr:d08",
            "status": "complete",
            "job_id": "job-1",
            "created_at": "2026-07-12T12:00:00Z",
            "updated_at": "2026-07-12T12:01:00Z",
        }
    )
    message = contracts.CoachMessage.model_validate(
        {
            "id": "message-1",
            "thread_id": "thread-1",
            "role": "coach",
            "content_md": "Answer",
            "created_at": "2026-07-12T12:01:00Z",
        }
    )

    assert review_output.measurement_assessment is None
    assert chat_output.measurement_assessment is None
    assert review.measurement_assessment is None
    assert message.measurement_assessment is None
