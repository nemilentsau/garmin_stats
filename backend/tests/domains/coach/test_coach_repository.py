"""Behavioral tests for coach persistence and queue invariants."""

from __future__ import annotations

import pytest

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.memory import (
    active_journal_entries,
    render_run_journal,
)
from app.domains.coach.contracts import (
    ArtifactRef,
    CoachThread,
    InitialReviewCandidate,
    JournalEntry,
    RunJournalSummary,
)
from app.domains.coach.schema import init_coach_schema
from app.infra import sqlite

NOW = "2026-07-12T12:00:00Z"
LATER = "2026-07-12T13:00:00Z"


def _thread(thread_id: str = "thread-1") -> CoachThread:
    return CoachThread(
        id=thread_id,
        title="Recovery question",
        status="open",
        created_at=NOW,
        last_activity_at=NOW,
    )


def _run_journal_summary() -> RunJournalSummary:
    return RunJournalSummary(
        purpose="Easy aerobic maintenance",
        outcome="completed_as_intended",
        takeaway="The intended maintenance stimulus was achieved.",
        decision_relevant_uncertainties=[],
        follow_up_triggers=[
            "Revisit only if delayed tissue response is abnormal."
        ],
        comparison_tags=["easy", "strides", "strap_hr"],
        refs=[ArtifactRef(kind="run", value="run-1")],
    )


def test_legacy_memory_remains_readable_but_is_not_current_policy_memory():
    legacy = JournalEntry(
        id="journal-v1",
        ts=NOW,
        kind="review",
        content_md="Legacy forensic compliance language.",
        refs=[],
        source_id="review-old",
    )

    assert legacy.policy_version == 1
    assert active_journal_entries([legacy], policy_version=2) == []


def test_run_memory_render_keeps_interpretation_and_refs_without_telemetry_table():
    rendered = render_run_journal(_run_journal_summary())

    assert "Purpose: Easy aerobic maintenance" in rendered
    assert "Outcome: completed as intended" in rendered
    assert "6.03 mi" not in rendered
    assert "run: run-1" in rendered


def test_schema_init_second_call_is_noop():
    with sqlite.connect() as connection:
        init_coach_schema(connection)
        init_coach_schema(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {
        "coach_reviews",
        "coach_threads",
        "coach_messages",
        "coach_journal",
        "coach_brief_versions",
        "coach_jobs",
        "coach_reconciliation_state",
    }.issubset(tables)


def test_repository_exposes_only_atomic_output_mutators():
    for method_name in [
        "update_review",
        "insert_message",
        "complete_job",
        "append_journal",
        "append_brief",
    ]:
        assert not hasattr(SqliteCoachRepository, method_name)


def test_run_review_and_job_are_created_in_one_transaction():
    repository = SqliteCoachRepository()

    review, job, created = repository.enqueue_run_review(
        run_id="run-1",
        date="2026-07-11",
        occurrence_key="occ-1",
    )

    assert created is True
    assert review.job_id == job.id
    assert review.status == "queued"
    assert job.kind == "review_run"
    assert job.payload["review_id"] == review.id
    assert repository.review(review.id) == review
    assert repository.job(job.id) == job


def test_duplicate_run_trigger_returns_existing_review_without_second_job():
    repository = SqliteCoachRepository()
    first_review, first_job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-11", occurrence_key=None
    )

    review, job, created = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-11", occurrence_key=None
    )

    assert created is False
    assert review.id == first_review.id
    assert job.id == first_job.id
    assert repository.queued_count() == 1


def test_duplicate_skip_trigger_returns_existing_review_without_second_job():
    repository = SqliteCoachRepository()
    first_review, first_job, _ = repository.enqueue_skip_review(
        date="2026-07-10", occurrence_key="run-am", card_name="Easy run"
    )

    review, job, created = repository.enqueue_skip_review(
        date="2026-07-10", occurrence_key="run-am", card_name="Easy run"
    )

    assert created is False
    assert review.id == first_review.id
    assert job.id == first_job.id
    assert repository.queued_count() == 1


def test_claim_next_job_prefers_priority_then_oldest_available():
    repository = SqliteCoachRepository()
    first_review, first_review_job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-10", occurrence_key=None
    )
    del first_review
    repository.enqueue_run_review(run_id="run-2", date="2026-07-11", occurrence_key=None)
    repository.insert_thread(_thread())
    _, chat_job = repository.enqueue_chat_message(
        thread_id="thread-1", content_md="How should I recover?"
    )

    claimed_chat = repository.claim_next_job("9999-01-01T00:00:00Z")
    claimed_review = repository.claim_next_job("9999-01-01T00:00:00Z")

    assert claimed_chat is not None
    assert claimed_chat.id == chat_job.id
    assert claimed_chat.status == "running"
    assert claimed_chat.attempt_count == 1
    assert claimed_review is not None
    assert claimed_review.id == first_review_job.id


def test_claim_ignores_future_and_nonqueued_jobs():
    repository = SqliteCoachRepository()
    _, job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-10", occurrence_key=None
    )
    repository.fail_job(job.id, error="temporary", finished_at=NOW)
    repository.retry_failed_job(job.id, available_at=LATER)

    assert repository.claim_next_job(NOW) is None

    claimed = repository.claim_next_job(LATER)
    assert claimed is not None
    assert repository.claim_next_job("9999-01-01T00:00:00Z") is None


def test_queue_utc_text_order_is_correct_across_dst_fallback_instants():
    repository = SqliteCoachRepository()
    _, first, _ = repository.enqueue_run_review(
        run_id="run-before-fallback", date="2026-10-31", occurrence_key=None
    )
    _, second, _ = repository.enqueue_run_review(
        run_id="run-after-fallback", date="2026-11-01", occurrence_key=None
    )
    for job, available_at in (
        (first, "2026-11-01T05:30:00Z"),
        (second, "2026-11-01T06:15:00Z"),
    ):
        repository.fail_job(job.id, error="deferred", finished_at=NOW)
        repository.retry_failed_job(job.id, available_at=available_at)

    claimed = repository.claim_next_job("2026-11-01T05:45:00Z")

    assert claimed is not None
    assert claimed.id == first.id
    assert repository.job(second.id).status == "queued"  # type: ignore[union-attr]


def test_retry_failed_job_requeues_same_job_and_review():
    repository = SqliteCoachRepository()
    review, job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-10", occurrence_key=None
    )
    repository.fail_job(job.id, error="invalid output", finished_at=NOW)

    retried = repository.retry_failed_job(job.id, available_at=LATER)

    updated_review = repository.review(review.id)
    assert retried.id == job.id
    assert retried.status == "queued"
    assert retried.error is None
    assert retried.attempt_count == 0
    assert updated_review is not None
    assert updated_review.status == "queued"
    assert updated_review.error is None


def test_retry_rejects_complete_or_running_job():
    repository = SqliteCoachRepository()
    _, running_job, _ = repository.enqueue_run_review(
        run_id="run-running", date="2026-07-10", occurrence_key=None
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None

    with pytest.raises(ValueError, match="failed"):
        repository.retry_failed_job(running_job.id, available_at=NOW)

def test_stale_running_job_below_attempt_limit_requeues():
    repository = SqliteCoachRepository()
    _, job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-10", occurrence_key=None
    )
    repository.claim_next_job("9999-01-01T00:00:00Z")

    changed = repository.recover_stale_jobs(cutoff="9999-01-01T00:00:00Z", max_attempts=3)

    assert [item.id for item in changed] == [job.id]
    assert changed[0].status == "queued"
    assert changed[0].attempt_count == 1


def test_stale_running_job_at_attempt_limit_fails():
    repository = SqliteCoachRepository()
    _, job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-10", occurrence_key=None
    )
    for _ in range(2):
        repository.claim_next_job("9999-01-01T00:00:00Z")
        repository.recover_stale_jobs(cutoff="9999-01-01T00:00:00Z", max_attempts=3)
    repository.claim_next_job("9999-01-01T00:00:00Z")

    changed = repository.recover_stale_jobs(cutoff="9999-01-01T00:00:00Z", max_attempts=3)

    assert [item.id for item in changed] == [job.id]
    assert changed[0].status == "failed"
    assert changed[0].attempt_count == 3


def test_initial_backfill_and_marker_commit_atomically_oldest_first():
    repository = SqliteCoachRepository()
    candidates = [
        InitialReviewCandidate(kind="run", date="2026-07-11", run_id="run-2"),
        InitialReviewCandidate(
            kind="skip",
            date="2026-07-09",
            occurrence_key="run-am",
            card_name="Easy run",
        ),
        InitialReviewCandidate(kind="run", date="2026-07-10", run_id="run-1"),
    ]

    jobs, created = repository.enqueue_initial_backfill(
        activation_date="2026-07-12", candidates=candidates
    )

    assert created is True
    assert [job.payload["date"] for job in jobs] == [
        "2026-07-09",
        "2026-07-10",
        "2026-07-11",
    ]
    assert repository.reconciliation_state().initial_backfill_done is True  # type: ignore[union-attr]
    assert repository.queued_count() == 3


def test_existing_reconciliation_state_prevents_second_historical_batch():
    repository = SqliteCoachRepository()
    initial = [InitialReviewCandidate(kind="run", date="2026-07-11", run_id="run-1")]
    repository.enqueue_initial_backfill(activation_date="2026-07-12", candidates=initial)

    jobs, created = repository.enqueue_initial_backfill(
        activation_date="2026-07-13",
        candidates=[InitialReviewCandidate(kind="run", date="2026-07-10", run_id="run-older")],
    )

    assert created is False
    assert jobs == []
    assert repository.review_for_run("run-older") is None
    assert repository.reconciliation_state().activation_date == "2026-07-12"  # type: ignore[union-attr]


def test_initial_backfill_rejects_more_than_three_without_partial_writes():
    repository = SqliteCoachRepository()
    candidates = [
        InitialReviewCandidate(kind="run", date=f"2026-07-0{day}", run_id=f"run-{day}")
        for day in range(1, 5)
    ]

    with pytest.raises(ValueError, match="three"):
        repository.enqueue_initial_backfill(activation_date="2026-07-12", candidates=candidates)

    assert repository.reconciliation_state() is None
    assert repository.queued_count() == 0


def test_status_queries_report_running_job_and_queued_count():
    repository = SqliteCoachRepository()
    repository.enqueue_run_review(run_id="run-1", date="2026-07-10", occurrence_key=None)
    repository.enqueue_run_review(run_id="run-2", date="2026-07-11", occurrence_key=None)

    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")

    assert claimed is not None
    assert repository.running_job() == claimed
    assert repository.queued_count() == 1
