"""Persistence and exact-target rules for coach measurement assessments."""

from __future__ import annotations

import pytest

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.contracts import (
    ArtifactRef,
    ChatOutput,
    CoachMeasurementAssessment,
    CoachThread,
    ReviewOutput,
)

NOW = "2026-07-12T12:00:00Z"
LATER = "2026-07-12T13:00:00Z"
OCCURRENCE_KEY = "running:lthr:d08"


def _assessment(
    *,
    run_id: str = "run-1",
    occurrence_key: str = OCCURRENCE_KEY,
    status: str = "valid",
) -> CoachMeasurementAssessment:
    return CoachMeasurementAssessment(
        run_id=run_id,
        occurrence_key=occurrence_key,
        status=status,  # type: ignore[arg-type]
        rationale="The protocol execution is credible for estimation.",
    )


def _review_output(
    assessment: CoachMeasurementAssessment | None,
) -> ReviewOutput:
    return ReviewOutput(
        verdict="compliant",
        review_md="Review",
        observations=[],
        concerns=[],
        suggestions=[],
        plan_adjustments=[],
        evidence_limits=[],
        plots_viewed=[],
        refs=[ArtifactRef(kind="run", value="run-1")],
        journal_entry_md="Journal",
        measurement_assessment=assessment,
    )


def _thread() -> CoachThread:
    return CoachThread(
        id="thread-1",
        title="Measurement",
        status="open",
        created_at=NOW,
        last_activity_at=NOW,
    )


def _running_review(repo: SqliteCoachRepository):
    review, _, _ = repo.enqueue_run_review(
        run_id="run-1", date="2026-07-12", occurrence_key=OCCURRENCE_KEY
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    repo.mark_review_generating(review.id, updated_at=NOW)
    return review, job


def _running_chat(repo: SqliteCoachRepository):
    repo.insert_thread(_thread())
    repo.enqueue_chat_message(thread_id="thread-1", content_md="Assess this run")
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    return job


def test_review_assessment_persists_in_same_completed_record():
    repo = SqliteCoachRepository()
    review, job = _running_review(repo)
    assessment = _assessment(status="provisional")

    repo.complete_review_output(
        review_id=review.id,
        job_id=job.id,
        output=_review_output(assessment),
        finished_at=LATER,
    )

    saved = repo.review(review.id)
    assert saved is not None
    assert saved.status == "complete"
    assert saved.measurement_assessment == assessment
    assert repo.job(job.id).status == "complete"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "assessment",
    [
        _assessment(occurrence_key="running:lthr:d15"),
        _assessment(run_id="run-2"),
    ],
    ids=["wrong-occurrence", "wrong-run"],
)
def test_review_assessment_wrong_target_rejects_entire_completion(
    assessment: CoachMeasurementAssessment,
):
    repo = SqliteCoachRepository()
    review, job = _running_review(repo)

    with pytest.raises(ValueError, match="queued review target"):
        repo.complete_review_output(
            review_id=review.id,
            job_id=job.id,
            output=_review_output(assessment),
            finished_at=LATER,
        )

    saved = repo.review(review.id)
    assert saved is not None
    assert saved.status == "generating"
    assert saved.measurement_assessment is None
    assert repo.job(job.id).status == "running"  # type: ignore[union-attr]
    assert repo.list_journal() == []


def test_skip_review_cannot_persist_run_measurement_assessment():
    repo = SqliteCoachRepository()
    review, _, _ = repo.enqueue_skip_review(
        date="2026-07-12",
        occurrence_key=OCCURRENCE_KEY,
        card_name="LTHR test",
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    repo.mark_review_generating(review.id, updated_at=NOW)

    with pytest.raises(ValueError, match="queued review target"):
        repo.complete_review_output(
            review_id=review.id,
            job_id=job.id,
            output=_review_output(_assessment()),
            finished_at=LATER,
        )

    saved = repo.review(review.id)
    assert saved is not None
    assert saved.status == "generating"
    assert saved.measurement_assessment is None
    assert repo.job(job.id).status == "running"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("refs", "assessment_run_id"),
    [
        ([], "run-1"),
        (
            [
                ArtifactRef(kind="run", value="run-1"),
                ArtifactRef(kind="run", value="run-2"),
            ],
            "run-1",
        ),
        ([ArtifactRef(kind="run", value="run-2")], "run-1"),
    ],
    ids=["zero-run-refs", "multiple-run-refs", "mismatched-run-ref"],
)
def test_chat_assessment_invalid_run_context_rejects_entire_completion(
    refs: list[ArtifactRef], assessment_run_id: str
):
    repo = SqliteCoachRepository()
    job = _running_chat(repo)
    output = ChatOutput(
        answer_md="Assessment",
        evidence_limits=[],
        refs=refs,
        measurement_assessment=_assessment(run_id=assessment_run_id),
    )

    with pytest.raises(ValueError, match="exactly one matching run reference"):
        repo.complete_chat_output(
            job_id=job.id,
            thread_id="thread-1",
            output=output,
            session_id=None,
            finished_at=LATER,
        )

    assert [message.role for message in repo.messages_for("thread-1")] == ["user"]
    assert repo.job(job.id).status == "running"  # type: ignore[union-attr]


def test_chat_assessment_persists_with_one_matching_run_reference():
    repo = SqliteCoachRepository()
    job = _running_chat(repo)
    assessment = _assessment(status="failed")

    message = repo.complete_chat_output(
        job_id=job.id,
        thread_id="thread-1",
        output=ChatOutput(
            answer_md="Assessment",
            evidence_limits=[],
            refs=[
                ArtifactRef(kind="date", value="2026-07-12"),
                ArtifactRef(kind="run", value="run-1"),
            ],
            measurement_assessment=assessment,
        ),
        session_id=None,
        finished_at=LATER,
    )

    assert message.measurement_assessment == assessment
    persisted = next(
        item for item in repo.messages_for("thread-1") if item.role == "coach"
    )
    assert persisted.measurement_assessment == assessment
    assert repo.job(job.id).status == "complete"  # type: ignore[union-attr]


def test_failed_jobs_persist_no_assessment():
    repo = SqliteCoachRepository()
    review, review_job = _running_review(repo)

    repo.fail_job(review_job.id, error="invalid output", finished_at=LATER)

    failed_review = repo.review(review.id)
    assert failed_review is not None
    assert failed_review.status == "failed"
    assert failed_review.measurement_assessment is None

    chat_job = _running_chat(repo)
    repo.fail_chat_output(
        job_id=chat_job.id,
        thread_id="thread-1",
        error="invalid output",
        finished_at=LATER,
    )
    failed_message = next(
        message for message in repo.messages_for("thread-1") if message.role == "system"
    )
    assert failed_message.measurement_assessment is None


def test_latest_assessment_read_prefers_newest_exact_successful_record():
    repo = SqliteCoachRepository()
    review, review_job = _running_review(repo)
    review_assessment = _assessment(status="provisional")
    repo.complete_review_output(
        review_id=review.id,
        job_id=review_job.id,
        output=_review_output(review_assessment),
        finished_at=NOW,
    )
    repo.insert_thread(_thread())
    repo.enqueue_chat_message(thread_id="thread-1", content_md="Reassess")
    chat_job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert chat_job is not None
    chat_assessment = _assessment(status="valid")
    chat_message = repo.complete_chat_output(
        job_id=chat_job.id,
        thread_id="thread-1",
        output=ChatOutput(
            answer_md="Updated assessment",
            evidence_limits=[],
            refs=[ArtifactRef(kind="run", value="run-1")],
            measurement_assessment=chat_assessment,
        ),
        session_id=None,
        finished_at=LATER,
    )
    repo.enqueue_chat_message(thread_id="thread-1", content_md="No reassessment")
    absent_job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert absent_job is not None
    repo.complete_chat_output(
        job_id=absent_job.id,
        thread_id="thread-1",
        output=ChatOutput(
            answer_md="No assessment",
            evidence_limits=[],
            refs=[],
        ),
        session_id=None,
        finished_at="2026-07-12T14:00:00Z",
    )
    repo.enqueue_chat_message(thread_id="thread-1", content_md="Assess another run")
    unrelated_job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert unrelated_job is not None
    repo.complete_chat_output(
        job_id=unrelated_job.id,
        thread_id="thread-1",
        output=ChatOutput(
            answer_md="Other run",
            evidence_limits=[],
            refs=[ArtifactRef(kind="run", value="run-2")],
            measurement_assessment=_assessment(run_id="run-2"),
        ),
        session_id=None,
        finished_at="2026-07-12T15:00:00Z",
    )

    record = repo.latest_measurement_assessment("run-1", OCCURRENCE_KEY)

    assert record is not None
    assert record.assessment == chat_assessment
    assert record.source_id == chat_message.id
    assert record.created_at == LATER
    assert repo.latest_measurement_assessment("run-1", "unrelated") is None

    repo.fail_job(chat_job.id, error="superseded output failed", finished_at=LATER)
    fallback = repo.latest_measurement_assessment("run-1", OCCURRENCE_KEY)
    assert fallback is not None
    assert fallback.assessment == review_assessment
    assert fallback.source_id == review.id
