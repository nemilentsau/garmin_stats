"""Behavioral tests for coach persistence and queue invariants."""

from __future__ import annotations

import json

import pytest

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.memory import (
    active_journal_entries,
    render_run_journal,
)
from app.domains.coach.contracts import (
    ArtifactRef,
    BriefUpdate,
    CoachThread,
    InitialReviewCandidate,
    JournalEntry,
    ReviewOutput,
    RunJournalSummary,
    safe_artifact_id,
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


def _review_output(
    takeaway: str = "Purpose achieved",
    *,
    follow_up_questions: list[str] | None = None,
) -> ReviewOutput:
    journal = _run_journal_summary().model_copy(update={"takeaway": takeaway})
    return ReviewOutput(
        outcome="completed_as_intended",
        confidence="high",
        review_md="The run achieved its intended purpose.",
        follow_up_questions=follow_up_questions or [],
        history_used=[],
        plot_observations=[],
        refs=[ArtifactRef(kind="run", value="run-1")],
        journal=journal,
        brief_update=BriefUpdate(action="keep", content_md=None),
    )


def _complete_review(
    repository: SqliteCoachRepository,
    *,
    finished_at: str = NOW,
    takeaway: str = "Purpose achieved",
    follow_up_questions: list[str] | None = None,
):
    review, _, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-14", occurrence_key="run-am"
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None
    repository.mark_review_generating(review.id, updated_at=NOW)
    repository.complete_review_output(
        review_id=review.id,
        job_id=claimed.id,
        output=_review_output(takeaway, follow_up_questions=follow_up_questions),
        finished_at=finished_at,
    )
    return review, claimed


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


def test_complete_review_can_be_requeued_without_reusing_attempt_directory():
    repository = SqliteCoachRepository()
    review, job = _complete_review(repository)

    regenerated = repository.regenerate_complete_review(
        review.id, available_at="2026-07-14T15:00:00Z"
    )

    assert regenerated.id == job.id
    assert regenerated.status == "queued"
    assert regenerated.attempt_count == 1
    assert repository.review(review.id).status == "queued"  # type: ignore[union-attr]


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_only_complete_review_can_be_regenerated(status: str):
    repository = SqliteCoachRepository()
    review, job, _ = repository.enqueue_run_review(
        run_id=f"run-{status}", date="2026-07-14", occurrence_key="run-am"
    )
    if status in {"running", "failed"}:
        claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
        assert claimed is not None
        repository.mark_review_generating(review.id, updated_at=NOW)
        if status == "failed":
            repository.fail_job(claimed.id, error="model failure", finished_at=NOW)
    with pytest.raises(ValueError, match="complete"):
        repository.regenerate_complete_review(review.id, available_at=NOW)
    assert repository.job(job.id) is not None


def test_regenerated_review_supersedes_prior_active_journal_entry():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository, takeaway="First judgment")
    repository.regenerate_complete_review(review.id, available_at=LATER)
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None
    repository.mark_review_generating(review.id, updated_at=LATER)
    repository.complete_review_output(
        review_id=review.id,
        job_id=claimed.id,
        output=_review_output("Corrected judgment"),
        finished_at="2026-07-14T16:00:00Z",
    )

    all_entries = repository.list_journal(policy_version=2)
    active = active_journal_entries(all_entries)

    assert len(all_entries) == 2
    assert len(active) == 1
    assert "Corrected judgment" in active[0].content_md
    assert active[0].supersedes_id == all_entries[0].id


def test_follow_up_questions_persist_on_completed_review():
    repository = SqliteCoachRepository()

    review, _ = _complete_review(
        repository, follow_up_questions=["Was the course flat?"]
    )

    saved = repository.review(review.id)
    assert saved is not None
    assert saved.follow_up_questions == ["Was the course flat?"]


def test_review_blob_migration_strips_plots_viewed_and_second_init_is_noop():
    legacy_data = json.dumps(
        {
            "id": "review-legacy",
            "date": "2026-07-10",
            "kind": "run",
            "run_id": "run-legacy",
            "occurrence_key": None,
            "status": "complete",
            "job_id": "job-legacy",
            "created_at": NOW,
            "updated_at": NOW,
            "plots_viewed": ["a.png"],
        }
    )
    with sqlite.connect() as connection:
        init_coach_schema(connection)
        connection.execute(
            """
            INSERT INTO coach_reviews
                (id, date, kind, run_id, occurrence_key, status, updated_at, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "review-legacy",
                "2026-07-10",
                "run",
                "run-legacy",
                None,
                "complete",
                NOW,
                legacy_data,
            ),
        )
        connection.commit()

        init_coach_schema(connection)
        connection.commit()
        stripped = connection.execute(
            "SELECT data FROM coach_reviews WHERE id = 'review-legacy'"
        ).fetchone()["data"]

        init_coach_schema(connection)
        connection.commit()
        rerun = connection.execute(
            "SELECT data FROM coach_reviews WHERE id = 'review-legacy'"
        ).fetchone()["data"]

    assert rerun == stripped

    repository = SqliteCoachRepository()
    loaded = repository.review("review-legacy")

    assert loaded is not None
    assert loaded.id == "review-legacy"
    assert loaded.follow_up_questions == []


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


def test_matching_run_supersedes_skip_and_removes_it_from_review_history():
    repository = SqliteCoachRepository()
    skip, _, _ = repository.enqueue_skip_review(
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
        card_name="LT intervals",
    )

    run, _, created = repository.enqueue_run_review(
        run_id="run-late",
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
    )

    saved_skip = repository.review(skip.id)
    assert created is True
    assert saved_skip is not None
    assert saved_skip.superseded_by_review_id == run.id
    assert repository.list_reviews(from_date=None, to_date=None, limit=10) == [run]


def test_existing_matching_run_prevents_later_skip_job():
    repository = SqliteCoachRepository()
    run, run_job, _ = repository.enqueue_run_review(
        run_id="run-first",
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
    )

    review, job, created = repository.enqueue_skip_review(
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
        card_name="LT intervals",
    )

    assert created is False
    assert review.id == run.id
    assert job.id == run_job.id
    assert repository.queued_count() == 1


def test_repeat_run_trigger_repairs_conflict_without_duplicate_job():
    repository = SqliteCoachRepository()
    skip, _, _ = repository.enqueue_skip_review(
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
        card_name="LT intervals",
    )
    run, run_job, _ = repository.enqueue_run_review(
        run_id="run-late",
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
    )

    repeated, repeated_job, created = repository.enqueue_run_review(
        run_id="run-late",
        date="2026-07-16",
        occurrence_key="running.v3:run.lt_intervals:d04",
    )

    assert created is False
    assert repeated.id == run.id
    assert repeated_job.id == run_job.id
    assert repository.review(skip.id).superseded_by_review_id == run.id  # type: ignore[union-attr]
    assert repository.queued_count() == 2


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


@pytest.mark.parametrize(
    "value",
    ["run-1", "review_42.md", "2026-07-12", "A1"],
)
def test_safe_artifact_id_accepts_charset_safe_values(value: str):
    assert safe_artifact_id(value) == value


@pytest.mark.parametrize(
    "value",
    ["", ".", "..", "a/b", "a\\b", "run 1", "run$1", "run!"],
)
def test_safe_artifact_id_rejects_empty_dot_slash_and_non_charset_values(value: str):
    with pytest.raises(ValueError, match="Unsafe artifact reference"):
        safe_artifact_id(value)
