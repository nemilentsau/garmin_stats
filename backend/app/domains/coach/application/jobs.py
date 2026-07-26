"""Explicit coach enqueue and thread-lifecycle policy."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.contracts import (
    CoachEnqueueResponse,
    CoachJob,
    CoachThread,
)
from app.domains.coach.read_gateway import (
    CoachReadGateway,
    training_card_for_run,
)
from app.domains.coach.time import utc_now_iso


class CoachJobs:
    def __init__(
        self,
        *,
        repo: SqliteCoachRepository,
        gateway: CoachReadGateway,
    ) -> None:
        self.repo = repo
        self.gateway = gateway

    def enqueue_run_review(self, run_id: str) -> CoachEnqueueResponse:
        detail = self.gateway.run_detail(run_id)
        card = training_card_for_run(
            self.gateway, run_id=run_id, session_date=detail.session.session_date
        )
        occurrence_key = card.occurrence_key if card is not None else None
        review, job, created = self.repo.enqueue_run_review(
            run_id=run_id,
            date=detail.session.session_date,
            occurrence_key=occurrence_key,
        )
        return CoachEnqueueResponse(created=created, job=job, review=review)

    def create_thread(self, title: str) -> CoachThread:
        now = utc_now_iso()
        thread = CoachThread(
            id=f"thread-{uuid4()}",
            title=title,
            status="open",
            created_at=now,
            last_activity_at=now,
        )
        self.repo.insert_thread(thread)
        return thread

    def get_or_create_review_thread(
        self, review_id: str
    ) -> tuple[CoachThread, bool]:
        return self.repo.get_or_create_review_thread(
            review_id, created_at=utc_now_iso()
        )

    def enqueue_message(
        self,
        thread_id: str,
        content_md: str,
        *,
        review_revision_requested: bool = False,
    ) -> CoachEnqueueResponse:
        message, job = self.repo.enqueue_chat_message(
            thread_id=thread_id,
            content_md=content_md,
            review_revision_requested=review_revision_requested,
        )
        return CoachEnqueueResponse(created=True, job=job, message=message)

    def close_thread(self, thread_id: str) -> CoachJob:
        thread = self.repo.thread(thread_id)
        if thread is None:
            raise LookupError(f"Unknown coach thread: {thread_id}")
        if thread.review_id is not None:
            raise ValueError("Review-linked conversations cannot be closed")
        return self._begin_close(thread, now=utc_now_iso())

    def retry_job(self, job_id: str) -> CoachJob:
        return self.repo.retry_failed_job(job_id, available_at=utc_now_iso())

    def retry_close(self, thread_id: str) -> CoachJob:
        thread = self.repo.thread(thread_id)
        if thread is None:
            raise LookupError(f"Unknown coach thread: {thread_id}")
        if thread.review_id is not None:
            raise ValueError("Review-linked conversations cannot be closed")
        if thread.status != "close_failed":
            raise ValueError("Only a close-failed thread can retry closing")
        job = self.repo.failed_distill_job(thread_id)
        now = utc_now_iso()
        self.repo.update_thread(
            thread.model_copy(update={"status": "closing", "last_activity_at": now})
        )

        def queue() -> CoachJob:
            # A close that failed before its job existed has nothing to requeue.
            if job is None:
                return self.repo.enqueue_distill(thread_id=thread_id)
            return self.repo.retry_failed_job(job.id, available_at=now)

        return self._queue_close_job(thread, now=now, queue=queue)

    def _begin_close(self, thread: CoachThread, *, now: str) -> CoachJob:
        """Mark an open thread `closing` and queue its distill job."""
        self.repo.mark_thread_closing(thread.id, updated_at=now)
        return self._queue_close_job(
            thread,
            now=now,
            queue=lambda: self.repo.enqueue_distill(thread_id=thread.id),
        )

    def _queue_close_job(
        self,
        thread: CoachThread,
        *,
        now: str,
        queue: Callable[[], CoachJob],
    ) -> CoachJob:
        """Queue the distill job of a thread already marked `closing`.

        Marking the thread and queueing its job are two transactions. A failure
        between them would strand the thread in `closing` with no job and no
        route back, so the thread falls back to `close_failed` — the one state
        retry-close accepts.
        """
        try:
            return queue()
        except Exception:
            self.repo.update_thread(
                thread.model_copy(
                    update={"status": "close_failed", "last_activity_at": now}
                )
            )
            raise

    def reconcile_idle_threads(self, *, now: str | None = None) -> list[CoachJob]:
        current = datetime.fromisoformat((now or utc_now_iso()).replace("Z", "+00:00"))
        cutoff = current.astimezone(UTC) - timedelta(hours=6)
        jobs: list[CoachJob] = []
        for thread in sorted(
            self.repo.list_threads(), key=lambda item: item.last_activity_at
        ):
            activity = datetime.fromisoformat(thread.last_activity_at.replace("Z", "+00:00"))
            if thread.status == "open" and activity.astimezone(UTC) <= cutoff:
                jobs.append(self._begin_close(thread, now=now or utc_now_iso()))
        return jobs
