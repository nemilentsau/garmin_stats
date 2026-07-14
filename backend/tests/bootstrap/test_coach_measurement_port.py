"""Bootstrap mapping from coach persistence to training's local assessment seam."""

from __future__ import annotations

from inspect import Parameter, signature
from typing import Any, cast

import pytest

from app.bootstrap.coach_measurement_port import CoachMeasurementAssessmentPort
from app.bootstrap.container import build_container
from app.domains.coach.contracts import (
    ArtifactRef,
    BriefUpdate,
    CoachMeasurementAssessment,
    ReviewOutput,
    RunJournalSummary,
)
from app.domains.training.contracts import TrainingMeasurementAssessment
from app.domains.training.dependencies import MeasurementAssessmentReadPort

OCCURRENCE_KEY = "running:lthr:d08"


def _complete_assessment(repo, *, status: str = "provisional"):
    review, _, _ = repo.enqueue_run_review(
        run_id="run-1",
        date="2026-07-12",
        occurrence_key=OCCURRENCE_KEY,
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    assessment = CoachMeasurementAssessment(
        run_id="run-1",
        occurrence_key=OCCURRENCE_KEY,
        status=status,  # type: ignore[arg-type]
        rationale="The evidence is usable with a small protocol caveat.",
    )
    repo.complete_review_output(
        review_id=review.id,
        job_id=job.id,
        output=ReviewOutput(
            outcome="completed_as_intended",
            confidence="high",
            review_md="Review",
            follow_up_questions=[],
            history_used=[],
            plots_viewed=[],
            refs=[ArtifactRef(kind="run", value="run-1")],
            journal=RunJournalSummary(
                purpose="Measurement run",
                outcome="completed_as_intended",
                takeaway="The training purpose was achieved.",
                decision_relevant_uncertainties=[],
                follow_up_triggers=[],
                comparison_tags=["measurement"],
                refs=[ArtifactRef(kind="run", value="run-1")],
            ),
            brief_update=BriefUpdate(action="keep", content_md=None),
            measurement_assessment=assessment,
        ),
        finished_at="2026-07-12T12:00:00Z",
    )
    return review, assessment


def test_training_contract_and_read_port_are_training_local():
    assessment = TrainingMeasurementAssessment(
        status="valid", rationale="Credible protocol.", source_id="review-1"
    )

    assert assessment.status == "valid"
    assert "latest_for" in MeasurementAssessmentReadPort.__dict__


def test_exact_assessment_lookup_requires_named_target_arguments():
    protocol_parameters = list(
        signature(MeasurementAssessmentReadPort.latest_for).parameters.values()
    )[1:]
    assert [parameter.kind for parameter in protocol_parameters] == [
        Parameter.KEYWORD_ONLY,
        Parameter.KEYWORD_ONLY,
        Parameter.KEYWORD_ONLY,
    ]

    build_container.cache_clear()
    port = CoachMeasurementAssessmentPort(build_container().coach_repo)
    positional_call = cast(Any, port.latest_for)
    with pytest.raises(TypeError):
        positional_call("missing", OCCURRENCE_KEY)
    assert port.latest_for(run_id="missing", occurrence_key=OCCURRENCE_KEY) is None


def test_bootstrap_port_maps_latest_coach_record_without_leaking_coach_contract():
    build_container.cache_clear()
    container = build_container()
    review, coach_assessment = _complete_assessment(container.coach_repo)

    mapped = container.training_measurement_assessment_port.latest_for(
        run_id="run-1",
        occurrence_key=OCCURRENCE_KEY,
    )

    assert isinstance(
        container.training_measurement_assessment_port,
        CoachMeasurementAssessmentPort,
    )
    assert mapped is not None
    assert mapped.status == coach_assessment.status
    assert mapped.rationale == coach_assessment.rationale
    assert mapped.source_id == review.id
    assert type(mapped).__module__ == "app.domains.training.contracts"


def test_bootstrap_port_returns_none_when_exact_target_has_no_assessment():
    build_container.cache_clear()
    container = build_container()
    port = CoachMeasurementAssessmentPort(container.coach_repo)

    assert port.latest_for(run_id="missing", occurrence_key=OCCURRENCE_KEY) is None


def test_bootstrap_port_passes_exclusive_assessment_cutoff():
    build_container.cache_clear()
    container = build_container()
    review, coach_assessment = _complete_assessment(container.coach_repo, status="valid")
    port = container.training_measurement_assessment_port

    before_completion = port.latest_for(
        run_id="run-1",
        occurrence_key=OCCURRENCE_KEY,
        before="2026-07-12T12:00:00Z",
    )
    after_completion = port.latest_for(
        run_id="run-1",
        occurrence_key=OCCURRENCE_KEY,
        before="2026-07-12T12:00:01Z",
    )

    assert before_completion is None
    assert after_completion is not None
    assert after_completion.status == coach_assessment.status
    assert after_completion.source_id == review.id
