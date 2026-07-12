"""SQLite persistence and atomic queue operations for the coach domain."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Literal
from uuid import uuid4

from app.domains.coach.contracts import (
    ArtifactRef,
    BriefVersion,
    ChatOutput,
    CoachJob,
    CoachMessage,
    CoachReconciliationState,
    CoachReview,
    CoachThread,
    DistillOutput,
    InitialReviewCandidate,
    JobKind,
    JournalEntry,
    ReviewKind,
    ReviewOutput,
)
from app.domains.coach.time import utc_now_iso
from app.infra.sqlite import connect

_PRIORITIES: dict[JobKind, int] = {
    "chat_turn": 0,
    "review_run": 10,
    "review_skip": 10,
    "distill_thread": 30,
}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _model_from_row[ModelT](model: type[ModelT], row: sqlite3.Row) -> ModelT:
    return model.model_validate_json(row["data"])  # type: ignore[union-attr]


def _review_from_row(row: sqlite3.Row) -> CoachReview:
    return _model_from_row(CoachReview, row)


def _job_from_row(row: sqlite3.Row) -> CoachJob:
    return _model_from_row(CoachJob, row)


def _save_review(connection: sqlite3.Connection, review: CoachReview) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO coach_reviews
            (id, date, kind, run_id, occurrence_key, status, updated_at, data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review.id,
            review.date,
            review.kind,
            review.run_id,
            review.occurrence_key,
            review.status,
            review.updated_at,
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
    kind: ReviewKind,
    date: str,
    run_id: str | None,
    occurrence_key: str | None,
    card_name: str | None = None,
) -> tuple[CoachReview, CoachJob, bool]:
    if kind == "run":
        existing_row = connection.execute(
            "SELECT data FROM coach_reviews WHERE kind = 'run' AND run_id = ?",
            (run_id,),
        ).fetchone()
        dedupe_key = f"review:run:{run_id}"
        job_kind: JobKind = "review_run"
    else:
        existing_row = connection.execute(
            """
            SELECT data FROM coach_reviews
            WHERE kind = 'skip' AND date = ? AND occurrence_key = ?
            """,
            (date, occurrence_key),
        ).fetchone()
        dedupe_key = f"review:skip:{date}:{occurrence_key}"
        job_kind = "review_skip"
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
    if run_id is not None:
        payload["run_id"] = run_id
    if occurrence_key is not None:
        payload["occurrence_key"] = occurrence_key
    if card_name is not None:
        payload["card_name"] = card_name
    review = CoachReview(
        id=review_id,
        date=date,
        kind=kind,
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
                kind="run",
                date=date,
                run_id=run_id,
                occurrence_key=occurrence_key,
            )
            connection.commit()
        return result

    def enqueue_skip_review(
        self,
        *,
        date: str,
        occurrence_key: str,
        card_name: str,
    ) -> tuple[CoachReview, CoachJob, bool]:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = _create_review_job(
                connection,
                kind="skip",
                date=date,
                run_id=None,
                occurrence_key=occurrence_key,
                card_name=card_name,
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

    def list_reviews(
        self,
        *,
        from_date: str | None,
        to_date: str | None,
        limit: int,
    ) -> list[CoachReview]:
        clauses: list[str] = []
        params: list[object] = []
        if from_date is not None:
            clauses.append("date >= ?")
            params.append(from_date)
        if to_date is not None:
            clauses.append("date <= ?")
            params.append(to_date)
        query = "SELECT data FROM coach_reviews"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY date DESC, updated_at DESC, id LIMIT ?"
        params.append(limit)
        with connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_review_from_row(row) for row in rows]

    def update_review(self, review: CoachReview) -> None:
        with connect() as connection, connection:
            if (
                connection.execute(
                    "SELECT 1 FROM coach_reviews WHERE id = ?", (review.id,)
                ).fetchone()
                is None
            ):
                raise LookupError(f"Unknown coach review: {review.id}")
            _save_review(connection, review)

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
        self._validate_artifact_refs(output.refs)
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
            completed_review = review.model_copy(
                update={
                    "status": "complete",
                    "verdict": output.verdict,
                    "content_md": output.review_md,
                    "refs": output.refs,
                    "plots_viewed": output.plots_viewed,
                    "error": None,
                    "updated_at": finished_at,
                }
            )
            _save_review(connection, completed_review)
            self._insert_journal_output(
                connection,
                content_md=output.journal_entry_md,
                refs=output.refs,
                kind="review",
                source_id=review_id,
                created_at=finished_at,
            )
            if output.brief_md is not None:
                self._insert_brief_output(
                    connection,
                    content_md=output.brief_md,
                    source_id=review_id,
                    created_at=finished_at,
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
                INSERT INTO coach_threads (id, status, last_activity_at, data)
                VALUES (?, ?, ?, ?)
                """,
                (
                    thread.id,
                    thread.status,
                    thread.last_activity_at,
                    thread.model_dump_json(),
                ),
            )

    def thread(self, thread_id: str) -> CoachThread | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT data FROM coach_threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return None if row is None else _model_from_row(CoachThread, row)

    def list_threads(self) -> list[CoachThread]:
        with connect() as connection:
            rows = connection.execute(
                "SELECT data FROM coach_threads ORDER BY last_activity_at DESC, id"
            ).fetchall()
        return [_model_from_row(CoachThread, row) for row in rows]

    def update_thread(self, thread: CoachThread) -> None:
        with connect() as connection, connection:
            result = connection.execute(
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
        self._validate_artifact_refs(output.refs)
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            if job.status != "running":
                raise ValueError(f"Coach job {job_id} is not running")
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
                job_id=job_id,
                created_at=finished_at,
            )
            self._insert_message(connection, message)
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
            )
            if output.brief_md is not None:
                self._insert_brief_output(
                    connection,
                    content_md=output.brief_md,
                    source_id=thread_id,
                    created_at=finished_at,
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
                payload={"thread_id": thread_id, "user_message_id": message_id},
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

    def insert_message(self, message: CoachMessage) -> None:
        with connect() as connection, connection:
            self._insert_message(connection, message)

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

    def complete_job(self, job_id: str, finished_at: str) -> None:
        self._replace_job_state(
            job_id,
            allowed={"running"},
            update={
                "status": "complete",
                "finished_at": finished_at,
                "updated_at": finished_at,
                "error": None,
            },
        )

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

    def append_journal(self, entry: JournalEntry) -> None:
        with connect() as connection, connection:
            connection.execute(
                "INSERT INTO coach_journal (id, ts, data) VALUES (?, ?, ?)",
                (entry.id, entry.ts, entry.model_dump_json()),
            )

    def list_journal(self, *, limit: int | None = None) -> list[JournalEntry]:
        with connect() as connection:
            if limit is None:
                rows = connection.execute(
                    "SELECT data FROM coach_journal ORDER BY ts, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT data FROM (
                        SELECT id, ts, data FROM coach_journal
                        ORDER BY ts DESC, id DESC LIMIT ?
                    ) ORDER BY ts, id
                    """,
                    (limit,),
                ).fetchall()
        return [_model_from_row(JournalEntry, row) for row in rows]

    def append_brief(self, version: BriefVersion) -> None:
        with connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO coach_brief_versions (id, created_at, data)
                VALUES (?, ?, ?)
                """,
                (version.id, version.created_at, version.model_dump_json()),
            )

    def current_brief(self) -> BriefVersion | None:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT data FROM coach_brief_versions
                ORDER BY created_at DESC, id DESC LIMIT 1
                """
            ).fetchone()
        return None if row is None else _model_from_row(BriefVersion, row)

    @staticmethod
    def _validate_artifact_refs(refs: list[ArtifactRef]) -> None:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for ref in refs:
            if not ref.value or any(character not in allowed for character in ref.value):
                raise ValueError(f"Unsafe artifact reference: {ref.value}")

    @staticmethod
    def _insert_journal_output(
        connection: sqlite3.Connection,
        *,
        content_md: str,
        refs: list[ArtifactRef],
        kind: Literal["review", "chat", "admonish"],
        source_id: str,
        created_at: str,
    ) -> None:
        entry = JournalEntry(
            id=_new_id("journal"),
            ts=created_at,
            kind=kind,
            content_md=content_md,
            refs=refs,
            source_id=source_id,
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
    ) -> None:
        brief = BriefVersion(
            id=_new_id("brief"),
            content_md=content_md,
            source_id=source_id,
            created_at=created_at,
        )
        connection.execute(
            "INSERT INTO coach_brief_versions (id, created_at, data) VALUES (?, ?, ?)",
            (brief.id, brief.created_at, brief.model_dump_json()),
        )

    def enqueue_initial_backfill(
        self,
        *,
        activation_date: str,
        candidates: list[InitialReviewCandidate],
    ) -> tuple[list[CoachJob], bool]:
        if len(candidates) > 3:
            raise ValueError("Initial coach backfill is limited to three items")
        self._validate_candidates(candidates)
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                candidate.date,
                candidate.kind,
                candidate.run_id or candidate.occurrence_key or "",
            ),
        )
        jobs: list[CoachJob] = []
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state_row = connection.execute(
                "SELECT 1 FROM coach_reconciliation_state WHERE singleton = 1"
            ).fetchone()
            if state_row is not None:
                connection.commit()
                return [], False
            for candidate in ordered:
                _, job, created = _create_review_job(
                    connection,
                    kind=candidate.kind,
                    date=candidate.date,
                    run_id=candidate.run_id,
                    occurrence_key=candidate.occurrence_key,
                    card_name=candidate.card_name,
                )
                if created:
                    jobs.append(job)
            connection.execute(
                """
                INSERT INTO coach_reconciliation_state
                    (singleton, activation_date, initial_backfill_done)
                VALUES (1, ?, 1)
                """,
                (activation_date,),
            )
            connection.commit()
        return jobs, True

    def reconciliation_state(self) -> CoachReconciliationState | None:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT activation_date, initial_backfill_done
                FROM coach_reconciliation_state WHERE singleton = 1
                """
            ).fetchone()
        if row is None:
            return None
        return CoachReconciliationState(
            activation_date=row["activation_date"],
            initial_backfill_done=bool(row["initial_backfill_done"]),
        )

    @staticmethod
    def _validate_candidates(candidates: Iterable[InitialReviewCandidate]) -> None:
        for candidate in candidates:
            if candidate.kind == "run" and candidate.run_id is None:
                raise ValueError("Run backfill candidate requires run_id")
            if candidate.kind == "skip" and (
                candidate.occurrence_key is None or candidate.card_name is None
            ):
                raise ValueError("Skip backfill candidate requires occurrence_key and card_name")

    @staticmethod
    def _job_in_connection(connection: sqlite3.Connection, job_id: str) -> CoachJob:
        row = connection.execute("SELECT data FROM coach_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise LookupError(f"Unknown coach job: {job_id}")
        return _job_from_row(row)

    def _replace_job_state(
        self,
        job_id: str,
        *,
        allowed: set[str],
        update: dict[str, object],
    ) -> CoachJob:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._job_in_connection(connection, job_id)
            if job.status not in allowed:
                raise ValueError(
                    f"Coach job {job_id} has status {job.status}; expected {sorted(allowed)}"
                )
            changed = job.model_copy(update=update)
            _save_job(connection, changed)
            connection.commit()
        return changed

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
