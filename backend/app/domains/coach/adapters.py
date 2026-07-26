"""SQLite persistence and atomic queue operations for the coach domain."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from app.domains.coach.application.memory import (
    CURRENT_MEMORY_POLICY_VERSION,
    active_journal_entries,
    render_run_journal,
)
from app.domains.coach.contracts import (
    ArtifactRef,
    BriefVersion,
    ChatOutput,
    CoachJob,
    CoachMeasurementAssessmentRecord,
    CoachMessage,
    CoachReview,
    CoachReviewRevision,
    CoachThread,
    DistillOutput,
    JobKind,
    JournalEntry,
    ReviewOutput,
    RunJournalSummary,
    safe_artifact_id,
)
from app.domains.coach.time import utc_cutoff_iso, utc_now_iso
from app.infra.sqlite import connect

_PRIORITIES: dict[JobKind, int] = {
    "chat_turn": 0,
    "review_run": 10,
    "distill_thread": 30,
}


class MeasurementAssessmentValidationError(ValueError):
    """A model assessment does not match the durable job target/context."""


class ReviewRevisionValidationError(ValueError):
    """A model attempted to revise a review without durable user authorization."""


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _model_from_row[ModelT](model: type[ModelT], row: sqlite3.Row) -> ModelT:
    return model.model_validate_json(row["data"])  # type: ignore[union-attr]


def _review_from_row(row: sqlite3.Row) -> CoachReview:
    return _model_from_row(CoachReview, row)


def _job_from_row(row: sqlite3.Row) -> CoachJob:
    return _model_from_row(CoachJob, row)


def _lifecycle_instant(value: str) -> datetime:
    """Parse canonical or legacy Coach lifecycle text as a UTC instant."""
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        # Lifecycle fields have always represented UTC, including naive legacy rows.
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(UTC)


def _save_review(connection: sqlite3.Connection, review: CoachReview) -> None:
    """Write a review row, freezing `assessment_effective_at` at the instant
    the review's *current* measurement-assessment status first appeared.

    `updated_at` moves with every revision; `assessment_effective_at` must not,
    except when the thing it dates actually changed: measurement history
    re-derives each past attempt day against that day's cutoff, so a moving
    instant would retroactively rewrite decisions already made. But a revision
    that adds a missing assessment, or flips its status (e.g. failed -> valid),
    introduces a genuinely new fact that must take effect at the revision
    instant, not retroactively at first completion -- otherwise it could
    silently deactivate an already-activated backup day.
    Comparison is by assessment *status* only, not the whole record: a
    rationale-only reword does not change what happened, so it must not move
    the instant (that mismatch was the original bug this column exists to fix).
    """
    stored = connection.execute(
        "SELECT assessment_effective_at, data FROM coach_reviews WHERE id = ?",
        (review.id,),
    ).fetchone()
    assessment_effective_at = None if stored is None else stored["assessment_effective_at"]
    prior_assessment = None if stored is None else _review_from_row(stored).measurement_assessment
    prior_status = None if prior_assessment is None else prior_assessment.status
    current_assessment = review.measurement_assessment
    current_status = None if current_assessment is None else current_assessment.status
    if review.status == "complete" and (
        assessment_effective_at is None or current_status != prior_status
    ):
        assessment_effective_at = review.updated_at
    connection.execute(
        """
        INSERT OR REPLACE INTO coach_reviews
            (id, date, kind, run_id, occurrence_key, status, updated_at,
             assessment_effective_at, data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review.id,
            review.date,
            review.kind,
            review.run_id,
            review.occurrence_key,
            review.status,
            review.updated_at,
            assessment_effective_at,
            review.model_dump_json(),
        ),
    )


def _save_job(connection: sqlite3.Connection, job: CoachJob) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO coach_jobs
            (id, kind, dedupe_key, priority, status, available_at, started_at,
             finished_at, created_at, updated_at, data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.id,
            job.kind,
            job.dedupe_key,
            job.priority,
            job.status,
            job.available_at,
            job.started_at,
            job.finished_at,
            job.created_at,
            job.updated_at,
            job.model_dump_json(),
        ),
    )


def _create_review_job(
    connection: sqlite3.Connection,
    *,
    date: str,
    run_id: str,
    occurrence_key: str | None,
) -> tuple[CoachReview, CoachJob, bool]:
    existing_row = connection.execute(
        "SELECT data FROM coach_reviews WHERE kind = 'run' AND run_id = ?",
        (run_id,),
    ).fetchone()
    dedupe_key = f"review:run:{run_id}"
    job_kind: JobKind = "review_run"
    if existing_row is not None:
        review = _review_from_row(existing_row)
        job_row = connection.execute(
            "SELECT data FROM coach_jobs WHERE id = ?", (review.job_id,)
        ).fetchone()
        if job_row is None:
            raise RuntimeError(f"Review {review.id} references missing job {review.job_id}")
        return review, _job_from_row(job_row), False

    now = utc_now_iso()
    review_id = _new_id("review")
    job_id = _new_id("job")
    payload: dict[str, object] = {
        "review_id": review_id,
        "date": date,
    }
    payload["run_id"] = run_id
    if occurrence_key is not None:
        payload["occurrence_key"] = occurrence_key
    review = CoachReview(
        id=review_id,
        date=date,
        kind="run",
        run_id=run_id,
        occurrence_key=occurrence_key,
        status="queued",
        job_id=job_id,
        created_at=now,
        updated_at=now,
    )
    job = CoachJob(
        id=job_id,
        kind=job_kind,
        dedupe_key=dedupe_key,
        priority=_PRIORITIES[job_kind],
        status="queued",
        payload=payload,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    _save_review(connection, review)
    _save_job(connection, job)
    return review, job, True
class SqliteCoachRepository:
    """Coach persistence adapter with transaction-owned queue invariants."""

    def enqueue_run_review(
        self,
        *,
        run_id: str,
        date: str,
        occurrence_key: str | None,
    ) -> tuple[CoachReview, CoachJob, bool]:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = _create_review_job(
                connection,
                date=date,
                run_id=run_id,
                occurrence_key=occurrence_key,
            )
            connection.commit()
        return result

    def review(self, review_id: str) -> CoachReview | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT data FROM coach_reviews WHERE id = ?", (review_id,)
            ).fetchone()
        return None if row is None else _review_from_row(row)

    def review_for_run(self, run_id: str) -> CoachReview | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT data FROM coach_reviews WHERE kind = 'run' AND run_id = ?",
                (run_id,),
            ).fetchone()
        return None if row is None else _review_from_row(row)

    def latest_measurement_assessment(
        self,
        run_id: str,
        occurrence_key: str,
        *,
        before: str | None = None,
    ) -> CoachMeasurementAssessmentRecord | None:
        """Return the newest exact successful assessment before an optional cutoff."""
        cutoff = utc_cutoff_iso(before)
        cutoff_instant = None if cutoff is None else _lifecycle_instant(cutoff)
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT source_id, created_at, source_kind, data FROM (
                    SELECT id AS source_id,
                           COALESCE(assessment_effective_at, updated_at) AS created_at,
                           'review' AS source_kind, data
                    FROM coach_reviews
                    WHERE status = 'complete'
                      AND json_extract(data, '$.measurement_assessment.run_id') = ?
                      AND json_extract(
                          data, '$.measurement_assessment.occurrence_key'
                      ) = ?
                    UNION ALL
                    SELECT message.id AS source_id, message.created_at,
                           'message' AS source_kind, message.data
                    FROM coach_messages AS message
                    JOIN coach_jobs AS job
                      ON job.id = json_extract(message.data, '$.job_id')
                    WHERE job.status = 'complete'
                      AND json_extract(message.data, '$.role') = 'coach'
                      AND json_extract(
                          message.data, '$.measurement_assessment.run_id'
                      ) = ?
                      AND json_extract(
                          message.data, '$.measurement_assessment.occurrence_key'
                      ) = ?
                )
                """,
                (
                    run_id,
                    occurrence_key,
                    run_id,
                    occurrence_key,
                ),
            ).fetchall()
        candidates: list[tuple[datetime, sqlite3.Row]] = []
        for row in rows:
            instant = _lifecycle_instant(row["created_at"])
            if cutoff_instant is None or instant < cutoff_instant:
                candidates.append((instant, row))
        if not candidates:
            return None
        _, row = max(
            candidates,
            key=lambda candidate: (
                candidate[0],
                str(candidate[1]["source_id"]),
            ),
        )
        source = (
            _model_from_row(CoachReview, row)
            if row["source_kind"] == "review"
            else _model_from_row(CoachMessage, row)
        )
        assessment = source.measurement_assessment
        if assessment is None:
            return None
        return CoachMeasurementAssessmentRecord(
            assessment=assessment,
            source_id=row["source_id"],
            created_at=row["created_at"],
        )

    def list_reviews(
        self,
        *,
        from_date: str | None,
        to_date: str | None,
        limit: int,
    ) -> list[CoachReview]:
        clauses: list[str] = ["kind = 'run'"]
        params: list[object] = []
        if from_date is not None:
            clauses.append("date >= ?")
            params.append(from_date)
        if to_date is not None:
            clauses.append("date <= ?")
            params.append(to_date)
        query = "SELECT data FROM coach_reviews WHERE " + " AND ".join(clauses)
        query += " ORDER BY date DESC, updated_at DESC, id LIMIT ?"
        params.append(limit)
        with connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_review_from_row(row) for row in rows]

    def mark_review_generating(self, review_id: str, *, updated_at: str) -> None:
        """Mark a claimed review as generating before external execution."""
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT data FROM coach_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown coach review: {review_id}")
            review = _review_from_row(row)
            _save_review(
                connection,
                review.model_copy(
                    update={"status": "generating", "updated_at": updated_at, "error": None}
                ),
            )
            connection.commit()

    def complete_review_output(
        self,
        *,
        review_id: str,
        job_id: str,
        output: ReviewOutput,
        finished_at: str,
    ) -> None:
        """Persist review, semantic memory, optional brief, and job atomically."""
        self._validate_artifact_refs(
            [
                *output.refs,
                *output.journal.refs,
                *[
                    ref
                    for historical_use in output.history_used
                    for ref in historical_use.refs
                ],
            ]
        )
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            if job.status != "running":
                raise ValueError(f"Coach job {job_id} is not running")
            row = connection.execute(
                "SELECT data FROM coach_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown coach review: {review_id}")
            review = _review_from_row(row)
            assessment = output.measurement_assessment
            if assessment is not None and (
                review.kind != "run"
                or assessment.run_id != review.run_id
                or assessment.occurrence_key != review.occurrence_key
                or assessment.run_id != job.payload.get("run_id")
                or assessment.occurrence_key != job.payload.get("occurrence_key")
            ):
                raise MeasurementAssessmentValidationError(
                    "Measurement assessment does not match queued review target"
                )
            completed_review = review.model_copy(
                update={
                    "status": "complete",
                    "outcome": output.outcome,
                    "confidence": output.confidence,
                    "content_md": output.review_md,
                    "refs": output.refs,
                    "follow_up_questions": list(output.follow_up_questions),
                    "plot_observations": output.plot_observations,
                    "history_used": output.history_used,
                    "measurement_assessment": assessment,
                    "error": None,
                    "updated_at": finished_at,
                }
            )
            _save_review(connection, completed_review)
            self._insert_review_revision(
                connection,
                review=completed_review,
                version=1,
                source_message_id=None,
                created_at=finished_at,
            )
            prior_rows = connection.execute(
                """
                SELECT data FROM coach_journal
                WHERE json_extract(data, '$.source_id') = ?
                  AND COALESCE(json_extract(data, '$.policy_version'), 1) = ?
                ORDER BY ts, id
                """,
                (review_id, CURRENT_MEMORY_POLICY_VERSION),
            ).fetchall()
            prior_entries = active_journal_entries(
                [_model_from_row(JournalEntry, row) for row in prior_rows]
            )
            self._insert_journal_output(
                connection,
                content_md=render_run_journal(output.journal),
                refs=output.journal.refs,
                kind="review",
                source_id=review_id,
                created_at=finished_at,
                policy_version=CURRENT_MEMORY_POLICY_VERSION,
                run_summary=output.journal,
                supersedes_id=(prior_entries[-1].id if prior_entries else None),
            )
            if output.brief_update.action == "replace":
                self._insert_brief_output(
                    connection,
                    content_md=output.brief_update.content_md or "",
                    source_id=review_id,
                    created_at=finished_at,
                    policy_version=CURRENT_MEMORY_POLICY_VERSION,
                )
            _save_job(
                connection,
                job.model_copy(
                    update={
                        "status": "complete",
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "error": None,
                    }
                ),
            )
            connection.commit()

    def insert_thread(self, thread: CoachThread) -> None:
        with connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO coach_threads (id, review_id, status, last_activity_at, data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    thread.id,
                    thread.review_id,
                    thread.status,
                    thread.last_activity_at,
                    thread.model_dump_json(),
                ),
            )

    def get_or_create_review_thread(
        self, review_id: str, *, created_at: str
    ) -> tuple[CoachThread, bool]:
        """Return the single durable conversation attached to a complete review."""
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            review_row = connection.execute(
                "SELECT data FROM coach_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if review_row is None:
                raise LookupError(f"Unknown coach review: {review_id}")
            review = _review_from_row(review_row)
            if review.status != "complete":
                raise ValueError("Only complete reviews can have conversations")
            existing = connection.execute(
                "SELECT data FROM coach_threads WHERE review_id = ?", (review_id,)
            ).fetchone()
            if existing is not None:
                thread = _model_from_row(CoachThread, existing)
                if thread.status != "open":
                    thread = thread.model_copy(
                        update={"status": "open", "last_activity_at": created_at}
                    )
                    connection.execute(
                        """
                        UPDATE coach_threads
                        SET status = ?, last_activity_at = ?, data = ?
                        WHERE id = ?
                        """,
                        (
                            thread.status,
                            thread.last_activity_at,
                            thread.model_dump_json(),
                            thread.id,
                        ),
                    )
                connection.commit()
                return thread, False
            thread = CoachThread(
                id=_new_id("thread"),
                title=f"Review · {review.date}",
                status="open",
                review_id=review_id,
                created_at=created_at,
                last_activity_at=created_at,
            )
            connection.execute(
                """
                INSERT INTO coach_threads (id, review_id, status, last_activity_at, data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    thread.id,
                    thread.review_id,
                    thread.status,
                    thread.last_activity_at,
                    thread.model_dump_json(),
                ),
            )
            connection.commit()
        return thread, True

    def thread(self, thread_id: str) -> CoachThread | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return None if row is None else _model_from_row(CoachThread, row)

    def thread_for_review(self, review_id: str) -> CoachThread | None:
        """Return an existing review thread without creating or reopening one."""
        with connect() as connection:
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE review_id = ?", (review_id,)
            ).fetchone()
        return None if row is None else _model_from_row(CoachThread, row)

    def list_threads(self) -> list[CoachThread]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT data FROM coach_threads
                WHERE review_id IS NULL
                ORDER BY last_activity_at DESC, id
                """
            ).fetchall()
        return [_model_from_row(CoachThread, row) for row in rows]

    def review_revisions(self, review_id: str) -> list[CoachReviewRevision]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT data FROM coach_review_revisions
                WHERE review_id = ?
                ORDER BY version
                """,
                (review_id,),
            ).fetchall()
        return [_model_from_row(CoachReviewRevision, row) for row in rows]

    def update_thread(self, thread: CoachThread) -> None:
        with connect() as connection, connection:
            result = connection.execute(
                """
                UPDATE coach_threads
                SET review_id = ?, status = ?, last_activity_at = ?, data = ?
                WHERE id = ?
                """,
                (
                    thread.review_id,
                    thread.status,
                    thread.last_activity_at,
                    thread.model_dump_json(),
                    thread.id,
                ),
            )
            if result.rowcount == 0:
                raise LookupError(f"Unknown coach thread: {thread.id}")

    def complete_chat_output(
        self,
        *,
        job_id: str,
        thread_id: str,
        output: ChatOutput,
        session_id: str | None,
        finished_at: str,
    ) -> CoachMessage:
        revision_output = output.review_revision
        self._validate_artifact_refs(
            [
                *output.refs,
                *([] if revision_output is None else revision_output.refs),
                *(
                    []
                    if revision_output is None
                    else [
                        ref
                        for historical_use in revision_output.history_used
                        for ref in historical_use.refs
                    ]
                ),
            ]
        )
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            if job.status != "running":
                raise ValueError(f"Coach job {job_id} is not running")
            assessment = output.measurement_assessment
            run_refs = [ref for ref in output.refs if ref.kind == "run"]
            if assessment is not None and (
                len(run_refs) != 1 or run_refs[0].value != assessment.run_id
            ):
                raise MeasurementAssessmentValidationError(
                    "Measurement assessment requires exactly one matching run reference"
                )
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown coach thread: {thread_id}")
            thread = _model_from_row(CoachThread, row)
            message = CoachMessage(
                id=_new_id("message"),
                thread_id=thread_id,
                role="coach",
                content_md=output.answer_md,
                refs=output.refs,
                measurement_assessment=assessment,
                job_id=job_id,
                created_at=finished_at,
            )
            self._insert_message(connection, message)
            if revision_output is not None:
                direct_plot_refs = {
                    ref.value for ref in revision_output.refs if ref.kind == "plot"
                }
                observation_plots = {
                    observation.plot
                    for observation in revision_output.plot_observations
                }
                if direct_plot_refs != observation_plots:
                    raise ReviewRevisionValidationError(
                        "Review revision plot evidence requires matching direct refs "
                        "and observations"
                    )
                if job.payload.get("review_revision_requested") is not True:
                    raise ReviewRevisionValidationError(
                        "Review revision requires an explicit correction request"
                    )
                if thread.review_id is None:
                    raise ReviewRevisionValidationError(
                        "Review revisions require a review-linked conversation"
                    )
                review_row = connection.execute(
                    "SELECT data FROM coach_reviews WHERE id = ?", (thread.review_id,)
                ).fetchone()
                if review_row is None:
                    raise LookupError(f"Unknown coach review: {thread.review_id}")
                review = _review_from_row(review_row)
                if review.status != "complete":
                    raise ValueError("Only complete reviews can be revised")
                revision_assessment = revision_output.measurement_assessment
                if revision_assessment is not None and (
                    review.kind != "run"
                    or revision_assessment.run_id != review.run_id
                    or revision_assessment.occurrence_key != review.occurrence_key
                ):
                    raise MeasurementAssessmentValidationError(
                        "Review revision assessment does not match the linked review target"
                    )
                version_row = connection.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) AS version
                    FROM coach_review_revisions WHERE review_id = ?
                    """,
                    (review.id,),
                ).fetchone()
                version = int(version_row["version"]) + 1
                revised = review.model_copy(
                    update={
                        "content_md": revision_output.content_md,
                        "outcome": revision_output.outcome,
                        "confidence": revision_output.confidence,
                        "refs": revision_output.refs,
                        "follow_up_questions": revision_output.follow_up_questions,
                        "plot_observations": revision_output.plot_observations,
                        "history_used": revision_output.history_used,
                        "measurement_assessment": revision_assessment,
                        "updated_at": finished_at,
                    }
                )
                _save_review(connection, revised)
                self._insert_review_revision(
                    connection,
                    review=revised,
                    version=version,
                    source_message_id=message.id,
                    created_at=finished_at,
                )
            changed_thread = thread.model_copy(
                update={
                    "codex_session_id": session_id or thread.codex_session_id,
                    "last_activity_at": finished_at,
                }
            )
            connection.execute(
                "UPDATE coach_threads SET last_activity_at = ?, data = ? WHERE id = ?",
                (finished_at, changed_thread.model_dump_json(), thread_id),
            )
            _save_job(
                connection,
                job.model_copy(
                    update={
                        "status": "complete",
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "error": None,
                    }
                ),
            )
            connection.commit()
        return message

    def fail_chat_output(
        self, *, job_id: str, thread_id: str, error: str, finished_at: str
    ) -> None:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            message = CoachMessage(
                id=_new_id("message"),
                thread_id=thread_id,
                role="system",
                content_md="The coach is temporarily unavailable. You can retry this turn.",
                job_id=job_id,
                created_at=finished_at,
            )
            self._insert_message(connection, message)
            _save_job(
                connection,
                job.model_copy(
                    update={
                        "status": "failed",
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "error": error,
                    }
                ),
            )
            connection.commit()

    def complete_distill_output(
        self,
        *,
        job_id: str,
        thread_id: str,
        output: DistillOutput,
        finished_at: str,
    ) -> None:
        self._validate_artifact_refs(output.refs)
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown coach thread: {thread_id}")
            thread = _model_from_row(CoachThread, row)
            self._insert_journal_output(
                connection,
                content_md=output.journal_entry_md,
                refs=output.refs,
                kind="chat",
                source_id=thread_id,
                created_at=finished_at,
                policy_version=CURRENT_MEMORY_POLICY_VERSION,
            )
            if output.brief_update.action == "replace":
                self._insert_brief_output(
                    connection,
                    content_md=output.brief_update.content_md or "",
                    source_id=thread_id,
                    created_at=finished_at,
                    policy_version=CURRENT_MEMORY_POLICY_VERSION,
                )
            changed_thread = thread.model_copy(
                update={"status": "closed", "last_activity_at": finished_at}
            )
            connection.execute(
                "UPDATE coach_threads SET status = ?, last_activity_at = ?, data = ? WHERE id = ?",
                (
                    changed_thread.status,
                    changed_thread.last_activity_at,
                    changed_thread.model_dump_json(),
                    thread_id,
                ),
            )
            _save_job(
                connection,
                job.model_copy(
                    update={
                        "status": "complete",
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "error": None,
                    }
                ),
            )
            connection.commit()

    def fail_distill_output(
        self, *, job_id: str, thread_id: str, error: str, finished_at: str
    ) -> None:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown coach thread: {thread_id}")
            thread = _model_from_row(CoachThread, row).model_copy(
                update={"status": "close_failed", "last_activity_at": finished_at}
            )
            connection.execute(
                "UPDATE coach_threads SET status = ?, last_activity_at = ?, data = ? WHERE id = ?",
                (thread.status, thread.last_activity_at, thread.model_dump_json(), thread_id),
            )
            _save_job(
                connection,
                job.model_copy(
                    update={
                        "status": "failed",
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "error": error,
                    }
                ),
            )
            connection.commit()

    def enqueue_chat_message(
        self,
        *,
        thread_id: str,
        content_md: str,
        review_revision_requested: bool = False,
    ) -> tuple[CoachMessage, CoachJob]:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            thread_row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if thread_row is None:
                raise LookupError(f"Unknown coach thread: {thread_id}")
            thread = _model_from_row(CoachThread, thread_row)
            if thread.status != "open":
                raise ValueError("Coach thread is not open")
            if review_revision_requested and (
                thread.review_id is None
                or not content_md.lstrip().casefold().startswith("update the review:")
            ):
                raise ReviewRevisionValidationError(
                    "Explicit review corrections must start with 'Update the review:'"
                )
            now = utc_now_iso()
            message_id = _new_id("message")
            job_id = _new_id("job")
            message = CoachMessage(
                id=message_id,
                thread_id=thread_id,
                role="user",
                content_md=content_md,
                job_id=job_id,
                created_at=now,
            )
            job = CoachJob(
                id=job_id,
                kind="chat_turn",
                dedupe_key=f"chat:{message_id}",
                priority=_PRIORITIES["chat_turn"],
                status="queued",
                payload={
                    "thread_id": thread_id,
                    "user_message_id": message_id,
                    "review_revision_requested": review_revision_requested,
                },
                available_at=now,
                created_at=now,
                updated_at=now,
            )
            self._insert_message(connection, message)
            _save_job(connection, job)
            updated_thread = thread.model_copy(update={"last_activity_at": now})
            connection.execute(
                """
                UPDATE coach_threads SET last_activity_at = ?, data = ? WHERE id = ?
                """,
                (now, updated_thread.model_dump_json(), thread_id),
            )
            connection.commit()
        return message, job

    def enqueue_distill(self, *, thread_id: str) -> CoachJob:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Unknown coach thread: {thread_id}")
            thread = _model_from_row(CoachThread, row)
            dedupe_key = f"distill:{thread_id}:{thread.last_activity_at}"
            existing = connection.execute(
                "SELECT data FROM coach_jobs WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
            if existing is not None:
                connection.commit()
                return _job_from_row(existing)
            now = utc_now_iso()
            job = CoachJob(
                id=_new_id("job"),
                kind="distill_thread",
                dedupe_key=dedupe_key,
                priority=_PRIORITIES["distill_thread"],
                status="queued",
                payload={"thread_id": thread_id},
                available_at=now,
                created_at=now,
                updated_at=now,
            )
            _save_job(connection, job)
            connection.commit()
        return job

    def mark_thread_closing(self, thread_id: str, *, updated_at: str) -> None:
        thread = self.thread(thread_id)
        if thread is None:
            raise LookupError(f"Unknown coach thread: {thread_id}")
        if thread.status != "open":
            raise ValueError("Only open coach threads can begin closing")
        self.update_thread(
            thread.model_copy(update={"status": "closing", "last_activity_at": updated_at})
        )

    @staticmethod
    def _insert_message(connection: sqlite3.Connection, message: CoachMessage) -> None:
        connection.execute(
            """
            INSERT INTO coach_messages (id, thread_id, created_at, data)
            VALUES (?, ?, ?, ?)
            """,
            (
                message.id,
                message.thread_id,
                message.created_at,
                message.model_dump_json(),
            ),
        )

    def messages_for(self, thread_id: str) -> list[CoachMessage]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT data FROM coach_messages
                WHERE thread_id = ? ORDER BY created_at, id
                """,
                (thread_id,),
            ).fetchall()
        return [_model_from_row(CoachMessage, row) for row in rows]

    def job(self, job_id: str) -> CoachJob | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT data FROM coach_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return None if row is None else _job_from_row(row)

    def running_job(self) -> CoachJob | None:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT data FROM coach_jobs
                WHERE status = 'running' ORDER BY started_at, id LIMIT 1
                """
            ).fetchone()
        return None if row is None else _job_from_row(row)

    def failed_distill_job(self, thread_id: str) -> CoachJob | None:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT data FROM coach_jobs
                WHERE kind = 'distill_thread' AND status = 'failed'
                  AND json_extract(data, '$.payload.thread_id') = ?
                ORDER BY updated_at DESC, id LIMIT 1
                """,
                (thread_id,),
            ).fetchone()
        return None if row is None else _job_from_row(row)

    def queued_count(self) -> int:
        with connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM coach_jobs WHERE status = 'queued'"
            ).fetchone()
        return 0 if row is None else int(row["total"])

    def claim_next_job(self, now: str) -> CoachJob | None:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT data FROM coach_jobs
                WHERE status = 'queued' AND available_at <= ?
                ORDER BY priority, created_at, id LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            job = _job_from_row(row)
            claimed = job.model_copy(
                update={
                    "status": "running",
                    "attempt_count": job.attempt_count + 1,
                    "started_at": now,
                    "finished_at": None,
                    "error": None,
                    "updated_at": now,
                }
            )
            _save_job(connection, claimed)
            connection.commit()
        return claimed

    def fail_job(self, job_id: str, *, error: str, finished_at: str) -> None:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            failed = job.model_copy(
                update={
                    "status": "failed",
                    "finished_at": finished_at,
                    "updated_at": finished_at,
                    "error": error,
                }
            )
            _save_job(connection, failed)
            self._update_associated_review(connection, failed, "failed", error)
            connection.commit()

    def retry_failed_job(self, job_id: str, *, available_at: str) -> CoachJob:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            if job.status != "failed":
                raise ValueError("Only failed coach jobs can be retried")
            retried = job.model_copy(
                update={
                    "status": "queued",
                    # A manual retry is a fresh decision by the user, so it gets
                    # the whole attempt budget back; `claim_next_job` would
                    # otherwise resume counting and burn the retry immediately.
                    "attempt_count": 0,
                    "available_at": available_at,
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "updated_at": available_at,
                }
            )
            _save_job(connection, retried)
            self._update_associated_review(connection, retried, "queued", None)
            connection.commit()
        return retried

    def recover_stale_jobs(
        self,
        *,
        cutoff: str,
        max_attempts: int,
    ) -> list[CoachJob]:
        changed: list[CoachJob] = []
        now = utc_now_iso()
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT data FROM coach_jobs
                WHERE status = 'running' AND started_at <= ?
                ORDER BY started_at, id
                """,
                (cutoff,),
            ).fetchall()
            for row in rows:
                job = _job_from_row(row)
                if job.attempt_count >= max_attempts:
                    updated = job.model_copy(
                        update={
                            "status": "failed",
                            "finished_at": now,
                            "updated_at": now,
                            "error": "Interrupted job exceeded recovery limit",
                        }
                    )
                    self._update_associated_review(connection, updated, "failed", updated.error)
                    self._fail_associated_thread(connection, updated, finished_at=now)
                else:
                    updated = job.model_copy(
                        update={
                            "status": "queued",
                            "available_at": now,
                            "started_at": None,
                            "finished_at": None,
                            "updated_at": now,
                            "error": None,
                        }
                    )
                    self._update_associated_review(connection, updated, "queued", None)
                _save_job(connection, updated)
                changed.append(updated)
            connection.commit()
        return changed

    def list_journal(
        self,
        *,
        limit: int | None = None,
        policy_version: int | None = None,
    ) -> list[JournalEntry]:
        where = ""
        params: list[object] = []
        if policy_version is not None:
            where = "WHERE COALESCE(json_extract(data, '$.policy_version'), 1) = ?"
            params.append(policy_version)
        with connect() as connection:
            if limit is None:
                rows = connection.execute(
                    f"SELECT data FROM coach_journal {where} ORDER BY ts, id",
                    params,
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT data FROM (
                        SELECT id, ts, data FROM coach_journal
                        {where}
                        ORDER BY ts DESC, id DESC LIMIT ?
                    ) ORDER BY ts, id
                    """,
                    [*params, limit],
                ).fetchall()
        return [_model_from_row(JournalEntry, row) for row in rows]

    def current_brief(
        self, *, policy_version: int | None = None
    ) -> BriefVersion | None:
        where = ""
        params: list[object] = []
        if policy_version is not None:
            where = "WHERE COALESCE(json_extract(data, '$.policy_version'), 1) = ?"
            params.append(policy_version)
        with connect() as connection:
            row = connection.execute(
                f"""
                SELECT data FROM coach_brief_versions
                {where}
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                params,
            ).fetchone()
        return None if row is None else _model_from_row(BriefVersion, row)

    @staticmethod
    def _validate_artifact_refs(refs: list[ArtifactRef]) -> None:
        for ref in refs:
            safe_artifact_id(ref.value)

    @staticmethod
    def _insert_journal_output(
        connection: sqlite3.Connection,
        *,
        content_md: str,
        refs: list[ArtifactRef],
        kind: Literal["review", "chat", "admonish"],
        source_id: str,
        created_at: str,
        policy_version: int,
        run_summary: RunJournalSummary | None = None,
        supersedes_id: str | None = None,
    ) -> None:
        entry = JournalEntry(
            id=_new_id("journal"),
            ts=created_at,
            kind=kind,
            content_md=content_md,
            refs=refs,
            source_id=source_id,
            policy_version=policy_version,
            supersedes_id=supersedes_id,
            run_summary=run_summary,
        )
        connection.execute(
            "INSERT INTO coach_journal (id, ts, data) VALUES (?, ?, ?)",
            (entry.id, entry.ts, entry.model_dump_json()),
        )

    @staticmethod
    def _insert_brief_output(
        connection: sqlite3.Connection,
        *,
        content_md: str,
        source_id: str,
        created_at: str,
        policy_version: int,
    ) -> None:
        brief = BriefVersion(
            id=_new_id("brief"),
            content_md=content_md,
            source_id=source_id,
            created_at=created_at,
            policy_version=policy_version,
        )
        connection.execute(
            "INSERT INTO coach_brief_versions (id, created_at, data) VALUES (?, ?, ?)",
            (brief.id, brief.created_at, brief.model_dump_json()),
        )

    @staticmethod
    def _insert_review_revision(
        connection: sqlite3.Connection,
        *,
        review: CoachReview,
        version: int,
        source_message_id: str | None,
        created_at: str,
    ) -> None:
        if (
            review.content_md is None
            or review.outcome is None
            or review.confidence is None
        ):
            raise ValueError("A review revision requires completed review content")
        revision = CoachReviewRevision(
            id=_new_id("revision"),
            review_id=review.id,
            version=version,
            content_md=review.content_md,
            outcome=review.outcome,
            confidence=review.confidence,
            refs=review.refs,
            follow_up_questions=review.follow_up_questions,
            plot_observations=review.plot_observations,
            history_used=review.history_used,
            measurement_assessment=review.measurement_assessment,
            snapshot_complete=True,
            source_message_id=source_message_id,
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO coach_review_revisions
                (id, review_id, version, created_at, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                revision.id,
                revision.review_id,
                revision.version,
                revision.created_at,
                revision.model_dump_json(),
            ),
        )

    @staticmethod
    def _job_in_connection(connection: sqlite3.Connection, job_id: str) -> CoachJob:
        row = connection.execute("SELECT data FROM coach_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise LookupError(f"Unknown coach job: {job_id}")
        return _job_from_row(row)

    @staticmethod
    def _update_associated_review(
        connection: sqlite3.Connection,
        job: CoachJob,
        status: str,
        error: str | None,
    ) -> None:
        review_id = job.payload.get("review_id")
        if not isinstance(review_id, str):
            return
        row = connection.execute(
            "SELECT data FROM coach_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Coach job {job.id} references missing review {review_id}")
        review = _review_from_row(row)
        updated = review.model_copy(
            update={"status": status, "error": error, "updated_at": job.updated_at}
        )
        _save_review(connection, updated)

    @staticmethod
    def _fail_associated_thread(
        connection: sqlite3.Connection,
        job: CoachJob,
        *,
        finished_at: str,
    ) -> None:
        """Move a hard-failed distill job's thread to the recoverable state.

        Mirrors the thread transition in `fail_distill_output`: a `closing`
        thread whose only distill job is gone can never reach `open`, `closed`,
        or retry-close, so recovery must leave it `close_failed`.
        """
        if job.kind != "distill_thread":
            return
        thread_id = job.payload.get("thread_id")
        if not isinstance(thread_id, str):
            return
        row = connection.execute(
            "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Coach job {job.id} references missing thread {thread_id}")
        thread = _model_from_row(CoachThread, row)
        if thread.status != "closing":
            # An already-closed thread means distillation landed; never resurrect it.
            return
        failed = thread.model_copy(
            update={"status": "close_failed", "last_activity_at": finished_at}
        )
        connection.execute(
            "UPDATE coach_threads SET status = ?, last_activity_at = ?, data = ? WHERE id = ?",
            (failed.status, failed.last_activity_at, failed.model_dump_json(), thread_id),
        )
