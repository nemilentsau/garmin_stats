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
    ChatOutput,
    CoachMeasurementAssessment,
    CoachThread,
    HistoricalEvidenceUse,
    JournalEntry,
    PlotObservation,
    ReviewOutput,
    ReviewRevisionOutput,
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


def test_follow_up_questions_persist_on_completed_review():
    repository = SqliteCoachRepository()

    review, _ = _complete_review(
        repository, follow_up_questions=["Was the course flat?"]
    )

    saved = repository.review(review.id)
    assert saved is not None
    assert saved.follow_up_questions == ["Was the course flat?"]


def test_completed_review_starts_immutable_revision_history():
    repository = SqliteCoachRepository()

    review, _ = _complete_review(repository)

    revisions = repository.review_revisions(review.id)
    assert len(revisions) == 1
    assert revisions[0].version == 1
    assert revisions[0].content_md == "The run achieved its intended purpose."
    assert revisions[0].snapshot_complete is True
    assert revisions[0].source_message_id is None


def test_legacy_revision_is_explicitly_marked_as_an_incomplete_snapshot():
    legacy_data = json.dumps(
        {
            "id": "revision-legacy",
            "review_id": "review-legacy",
            "version": 1,
            "content_md": "Legacy narrative only.",
            "outcome": "completed_as_intended",
            "confidence": "moderate",
            "refs": [],
            "created_at": NOW,
        }
    )
    with sqlite.connect() as connection:
        init_coach_schema(connection)
        connection.execute(
            """
            INSERT INTO coach_review_revisions
                (id, review_id, version, created_at, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("revision-legacy", "review-legacy", 1, NOW, legacy_data),
        )
        connection.commit()

    revision = SqliteCoachRepository().review_revisions("review-legacy")[0]

    assert revision.snapshot_complete is False


def _completed_at(review_id: str) -> str | None:
    with sqlite.connect() as connection:
        row = connection.execute(
            "SELECT completed_at FROM coach_reviews WHERE id = ?", (review_id,)
        ).fetchone()
    return None if row is None else row["completed_at"]


def test_review_completed_at_column_is_added_to_a_pre_existing_table():
    with sqlite.connect() as connection:
        connection.execute("DROP TABLE coach_reviews")
        connection.execute(
            """
            CREATE TABLE coach_reviews (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                kind TEXT NOT NULL,
                run_id TEXT,
                occurrence_key TEXT,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        connection.commit()

    with sqlite.connect() as connection:
        init_coach_schema(connection)
        connection.commit()
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(coach_reviews)")
        }

    assert "completed_at" in columns


def test_review_completed_at_backfills_from_the_first_revision_once():
    """Rows written before `completed_at` existed keep their original instant."""
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository, finished_at=NOW)
    with sqlite.connect() as connection:
        connection.execute(
            "UPDATE coach_reviews SET completed_at = NULL, updated_at = ? WHERE id = ?",
            (LATER, review.id),
        )
        connection.commit()

    with sqlite.connect() as connection:
        init_coach_schema(connection)
        connection.commit()
    backfilled = _completed_at(review.id)
    with sqlite.connect() as connection:
        init_coach_schema(connection)
        connection.commit()

    assert backfilled == NOW
    assert _completed_at(review.id) == backfilled


def test_linked_review_thread_is_reused_and_hidden_from_general_conversations():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository)

    assert repository.thread_for_review(review.id) is None
    first, first_created = repository.get_or_create_review_thread(
        review.id, created_at=NOW
    )
    second, second_created = repository.get_or_create_review_thread(
        review.id, created_at=LATER
    )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert second.review_id == review.id
    assert repository.thread_for_review(review.id) == first
    assert repository.list_threads() == []


def test_linked_chat_only_changes_review_for_explicit_revision_output():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(
        repository, follow_up_questions=["Was the course flat?"]
    )
    thread, _ = repository.get_or_create_review_thread(review.id, created_at=NOW)

    _, ordinary_job = repository.enqueue_chat_message(
        thread_id=thread.id, content_md="Why did you reach that conclusion?"
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None and claimed.id == ordinary_job.id
    repository.complete_chat_output(
        job_id=claimed.id,
        thread_id=thread.id,
        output=ChatOutput(
            answer_md="Because the easy-day stimulus stayed controlled.",
            refs=[ArtifactRef(kind="run", value="run-1")],
        ),
        session_id="session-1",
        finished_at=LATER,
    )
    assert len(repository.review_revisions(review.id)) == 1
    assert repository.review(review.id).content_md == (  # type: ignore[union-attr]
        "The run achieved its intended purpose."
    )

    _, correction_job = repository.enqueue_chat_message(
        thread_id=thread.id,
        content_md="Update the review: I stopped because air quality became unsafe.",
        review_revision_requested=True,
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None and claimed.id == correction_job.id
    coach_message = repository.complete_chat_output(
        job_id=claimed.id,
        thread_id=thread.id,
        output=ChatOutput(
            answer_md="I updated the review with the air-quality context.",
            refs=[ArtifactRef(kind="run", value="run-1")],
            review_revision=ReviewRevisionOutput(
                content_md="The run ended early because air quality became unsafe.",
                outcome="completed_with_material_deviation",
                confidence="high",
                refs=[
                    ArtifactRef(kind="run", value="run-1"),
                    ArtifactRef(kind="plot", value="air-quality.png"),
                ],
                follow_up_questions=[],
                plot_observations=[
                    PlotObservation(
                        plot="air-quality.png",
                        observation="The trace ends when the air-quality alert occurred.",
                    )
                ],
                history_used=[
                    HistoricalEvidenceUse(
                        run_id="run-previous",
                        role="recent_clean",
                        reason="Shows the expected complete aerobic duration.",
                        refs=[ArtifactRef(kind="run", value="run-previous")],
                    )
                ],
                measurement_assessment=CoachMeasurementAssessment(
                    run_id="run-1",
                    occurrence_key="run-am",
                    status="failed",
                    rationale="Unsafe air ended the measurement before completion.",
                ),
            ),
        ),
        session_id="session-1",
        finished_at="2026-07-12T14:00:00Z",
    )

    revisions = repository.review_revisions(review.id)
    assert [item.version for item in revisions] == [1, 2]
    assert revisions[-1].source_message_id == coach_message.id
    saved = repository.review(review.id)
    assert saved is not None
    assert saved.content_md == (
        "The run ended early because air quality became unsafe."
    )
    assert saved.follow_up_questions == []
    assert saved.plot_observations == revisions[-1].plot_observations
    assert saved.history_used == revisions[-1].history_used
    assert saved.measurement_assessment == revisions[-1].measurement_assessment


def test_review_revision_is_rejected_without_durable_user_correction_intent():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository)
    thread, _ = repository.get_or_create_review_thread(review.id, created_at=NOW)
    _, job = repository.enqueue_chat_message(
        thread_id=thread.id,
        content_md="Why did you reach that conclusion?",
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None and claimed.id == job.id

    with pytest.raises(ValueError, match="explicit correction request"):
        repository.complete_chat_output(
            job_id=claimed.id,
            thread_id=thread.id,
            output=ChatOutput(
                answer_md="I changed it.",
                refs=[ArtifactRef(kind="run", value="run-1")],
                review_revision=ReviewRevisionOutput(
                    content_md="Changed without authorization.",
                    outcome="completed_with_material_deviation",
                    confidence="low",
                    refs=[ArtifactRef(kind="run", value="run-1")],
                    follow_up_questions=[],
                    plot_observations=[],
                    history_used=[],
                ),
            ),
            session_id="session-1",
            finished_at=LATER,
        )

    assert len(repository.review_revisions(review.id)) == 1
    assert repository.review(review.id).content_md == (  # type: ignore[union-attr]
        "The run achieved its intended purpose."
    )


def test_review_revision_rejects_plot_refs_without_matching_observations():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository)
    thread, _ = repository.get_or_create_review_thread(review.id, created_at=NOW)
    repository.enqueue_chat_message(
        thread_id=thread.id,
        content_md="Update the review: use the corrected plot.",
        review_revision_requested=True,
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None

    with pytest.raises(ValueError, match="plot evidence"):
        repository.complete_chat_output(
            job_id=claimed.id,
            thread_id=thread.id,
            output=ChatOutput(
                answer_md="I updated the review.",
                refs=[ArtifactRef(kind="run", value="run-1")],
                review_revision=ReviewRevisionOutput(
                    content_md="Corrected review.",
                    outcome="completed_as_intended",
                    confidence="high",
                    refs=[ArtifactRef(kind="plot", value="corrected.png")],
                    follow_up_questions=[],
                    plot_observations=[],
                    history_used=[],
                ),
            ),
            session_id="session-1",
            finished_at=LATER,
        )

    assert len(repository.review_revisions(review.id)) == 1


def test_review_revision_rejects_measurement_assessment_for_another_occurrence():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository)
    thread, _ = repository.get_or_create_review_thread(review.id, created_at=NOW)
    repository.enqueue_chat_message(
        thread_id=thread.id,
        content_md="Update the review: correct the measurement assessment.",
        review_revision_requested=True,
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None

    with pytest.raises(ValueError, match="linked review target"):
        repository.complete_chat_output(
            job_id=claimed.id,
            thread_id=thread.id,
            output=ChatOutput(
                answer_md="I updated the review.",
                refs=[ArtifactRef(kind="run", value="run-1")],
                review_revision=ReviewRevisionOutput(
                    content_md="Corrected review.",
                    outcome="completed_as_intended",
                    confidence="high",
                    refs=[ArtifactRef(kind="run", value="run-1")],
                    follow_up_questions=[],
                    plot_observations=[],
                    history_used=[],
                    measurement_assessment=CoachMeasurementAssessment(
                        run_id="run-1",
                        occurrence_key="run-pm",
                        status="valid",
                        rationale="This assessment points at the wrong occurrence.",
                    ),
                ),
            ),
            session_id="session-1",
            finished_at=LATER,
        )

    assert len(repository.review_revisions(review.id)) == 1


def test_existing_closed_review_thread_is_reopened_for_future_corrections():
    repository = SqliteCoachRepository()
    review, _ = _complete_review(repository)
    thread, _ = repository.get_or_create_review_thread(review.id, created_at=NOW)
    repository.update_thread(thread.model_copy(update={"status": "closed"}))

    reopened, created = repository.get_or_create_review_thread(
        review.id, created_at=LATER
    )

    assert created is False
    assert reopened.id == thread.id
    assert reopened.status == "open"


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
        "coach_review_revisions",
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

def test_manual_retry_restores_the_full_attempt_budget():
    repository = SqliteCoachRepository()
    _, job, _ = repository.enqueue_run_review(
        run_id="run-1", date="2026-07-10", occurrence_key=None
    )
    claimed = repository.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None
    assert claimed.attempt_count == 1
    repository.fail_job(job.id, error="invalid output", finished_at=NOW)

    retried = repository.retry_failed_job(job.id, available_at=LATER)

    assert retried.attempt_count == 0
    reclaimed = repository.claim_next_job(LATER)
    assert reclaimed is not None
    assert reclaimed.attempt_count == 1


def _closing_thread_distill_job(repository: SqliteCoachRepository):
    repository.insert_thread(_thread())
    repository.mark_thread_closing("thread-1", updated_at=NOW)
    job = repository.enqueue_distill(thread_id="thread-1")
    assert repository.claim_next_job("9999-01-01T00:00:00Z") is not None
    return job


def test_stale_distill_job_at_attempt_limit_fails_the_owning_thread():
    repository = SqliteCoachRepository()
    job = _closing_thread_distill_job(repository)

    changed = repository.recover_stale_jobs(cutoff="9999-01-01T00:00:00Z", max_attempts=1)

    assert [item.status for item in changed] == ["failed"]
    thread = repository.thread("thread-1")
    assert thread is not None
    assert thread.status == "close_failed"
    failed_job = repository.failed_distill_job("thread-1")
    assert failed_job is not None
    assert failed_job.id == job.id


def test_stale_distill_job_below_attempt_limit_keeps_the_thread_closing():
    repository = SqliteCoachRepository()
    _closing_thread_distill_job(repository)

    changed = repository.recover_stale_jobs(cutoff="9999-01-01T00:00:00Z", max_attempts=3)

    assert [item.status for item in changed] == ["queued"]
    thread = repository.thread("thread-1")
    assert thread is not None
    assert thread.status == "closing"


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
