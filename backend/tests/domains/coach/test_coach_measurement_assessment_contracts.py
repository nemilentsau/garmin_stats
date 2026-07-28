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


def test_plot_observation_requires_basename_and_concrete_observation():
    observation = contracts.PlotObservation(
        plot="current-run-p01.png",
        observation="Pace and power rise together in six short late-run efforts.",
    )

    assert observation.plot == "current-run-p01.png"
    with pytest.raises(ValidationError):
        contracts.PlotObservation(plot="current/current-run-p01.png", observation="Used")
    with pytest.raises(ValidationError):
        contracts.PlotObservation(plot="current-run-p01.png", observation="   ")


def test_plot_observation_enforces_bounded_evidence_statement():
    assert len(
        contracts.PlotObservation(plot="current-run-p01.png", observation="x" * 300)
        .observation
    ) == 300
    with pytest.raises(ValidationError):
        contracts.PlotObservation(
            plot="current-run-p01.png", observation="x" * 301
        )


def test_outputs_and_durable_records_accept_absent_assessment_for_compatibility():
    review_output = contracts.ReviewOutput(
        headline="Controlled easy day; recovery on track.",
        outcome="completed_as_intended",
        confidence="high",
        review_md="Review",
        follow_up_questions=[],
        history_used=[],
        plot_observations=[],
        refs=[contracts.ArtifactRef(kind="run", value="run-1")],
        journal=contracts.RunJournalSummary(
            purpose="Measurement run",
            outcome="completed_as_intended",
            takeaway="The training purpose was achieved.",
            decision_relevant_uncertainties=[],
            follow_up_triggers=[],
            comparison_tags=["measurement"],
            refs=[contracts.ArtifactRef(kind="run", value="run-1")],
        ),
        brief_update=contracts.BriefUpdate(action="keep", content_md=None),
    )
    chat_output = contracts.ChatOutput(answer_md="Answer", refs=[])
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


def test_new_review_output_separates_outcome_confidence_and_history():
    output = contracts.ReviewOutput.model_validate(
        {
            "headline": "Controlled easy day; recovery on track.",
            "outcome": "completed_as_intended",
            "confidence": "moderate",
            "review_md": "The run achieved its easy aerobic purpose.",
            "follow_up_questions": [],
            "history_used": [],
            "plot_observations": [
                {
                    "plot": "current-run-p01.png",
                    "observation": "Six controlled pace surges are visible late in the run.",
                }
            ],
            "refs": [{"kind": "run", "value": "run-1"}],
            "journal": {
                "purpose": "Easy aerobic maintenance with strides",
                "outcome": "completed_as_intended",
                "takeaway": "The intended maintenance stimulus was achieved.",
                "decision_relevant_uncertainties": [],
                "follow_up_triggers": [
                    "Revisit only if delayed tissue response is abnormal."
                ],
                "comparison_tags": ["easy", "strides", "strap_hr"],
                "refs": [{"kind": "run", "value": "run-1"}],
            },
            "brief_update": {"action": "keep", "content_md": None},
            "measurement_assessment": None,
        }
    )

    assert output.outcome == "completed_as_intended"
    assert output.confidence == "moderate"
    assert output.brief_update.action == "keep"
    assert output.plot_observations[0].plot == "current-run-p01.png"
    assert not hasattr(output, "concerns")
    assert not hasattr(output, "evidence_limits")


def test_brief_keep_rejects_content_and_replace_requires_content():
    with pytest.raises(ValidationError):
        contracts.BriefUpdate(action="keep", content_md="Do not accept this")
    with pytest.raises(ValidationError):
        contracts.BriefUpdate(action="replace", content_md=None)


def test_existing_review_with_legacy_verdict_remains_readable():
    review = contracts.CoachReview.model_validate(
        {
            "id": "review-old",
            "date": "2026-07-14",
            "kind": "run",
            "run_id": "run-old",
            "occurrence_key": None,
            "status": "complete",
            "verdict": "partial",
            "outcome": None,
            "confidence": None,
            "content_md": "Legacy review",
            "refs": [],
            "history_used": [],
            "measurement_assessment": None,
            "job_id": "job-old",
            "error": None,
            "created_at": "2026-07-14T12:00:00Z",
            "updated_at": "2026-07-14T12:00:00Z",
        }
    )

    assert review.verdict == "partial"
    assert review.outcome is None
    assert review.plot_observations == []
    assert review.follow_up_questions == []


def test_review_rejects_legacy_plots_viewed_key():
    with pytest.raises(ValidationError):
        contracts.CoachReview.model_validate(
            {
                "id": "review-legacy",
                "date": "2026-07-14",
                "kind": "run",
                "run_id": "run-old",
                "occurrence_key": None,
                "status": "complete",
                "job_id": "job-old",
                "created_at": "2026-07-14T12:00:00Z",
                "updated_at": "2026-07-14T12:00:00Z",
                "plots_viewed": ["a.png"],
            }
        )
