"""Idempotent coach enqueue, reconciliation, and thread-lifecycle policy."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.contracts import (
    CoachEnqueueResponse,
    CoachJob,
    CoachThread,
    InitialReviewCandidate,
)
from app.domains.coach.read_gateway import (
    CoachReadGateway,
    TrainingTodayResponse,
    training_card_for_run,
)
from app.domains.coach.time import local_today_iso, utc_now_iso

# Ongoing reconciliation scans at most this many days back from today, even if the
# saved activation date is older. Runs sync at least daily, so a healthy deployment
# never needs a longer lookback; wider gaps were only possible during the
# initial-backfill era before this bound existed.
_RECONCILE_LOOKBACK_DAYS = 30


class CoachJobs:
    def __init__(
        self,
        *,
        repo: SqliteCoachRepository,
        gateway: CoachReadGateway,
        local_today=None,
    ) -> None:
        self.repo = repo
        self.gateway = gateway
        self.local_today = local_today or local_today_iso

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

    def enqueue_message(self, thread_id: str, content_md: str) -> CoachEnqueueResponse:
        message, job = self.repo.enqueue_chat_message(
            thread_id=thread_id, content_md=content_md
        )
        return CoachEnqueueResponse(created=True, job=job, message=message)

    def close_thread(self, thread_id: str) -> CoachJob:
        now = utc_now_iso()
        self.repo.mark_thread_closing(thread_id, updated_at=now)
        return self.repo.enqueue_distill(thread_id=thread_id)

    def retry_job(self, job_id: str) -> CoachJob:
        return self.repo.retry_failed_job(job_id, available_at=utc_now_iso())

    def regenerate_review(self, review_id: str) -> CoachJob:
        return self.repo.regenerate_complete_review(
            review_id, available_at=utc_now_iso()
        )

    def retry_close(self, thread_id: str) -> CoachJob:
        thread = self.repo.thread(thread_id)
        if thread is None:
            raise LookupError(f"Unknown coach thread: {thread_id}")
        if thread.status != "close_failed":
            raise ValueError("Only a close-failed thread can retry closing")
        job = self.repo.failed_distill_job(thread_id)
        if job is None:
            raise LookupError(f"No failed close job for thread: {thread_id}")
        now = utc_now_iso()
        self.repo.update_thread(
            thread.model_copy(update={"status": "closing", "last_activity_at": now})
        )
        return self.repo.retry_failed_job(job.id, available_at=now)

    def reconcile_pending(self) -> list[CoachJob]:
        """Enqueue reviews/skips for evidence that has appeared since the last pass.

        The post-activation scan window is bounded to the last
        `_RECONCILE_LOOKBACK_DAYS` days (never before the saved activation date).
        Runs sync at least daily, so a healthy deployment never needs more than a
        30-day lookback; an unbounded activation-to-today scan was only load-bearing
        during the initial-backfill era, before per-run/per-day dedupe existed.
        """
        today = date.fromisoformat(self.local_today())
        state = self.repo.reconciliation_state()
        runs = self.gateway.recent_runs(evidence_date=today.isoformat(), limit=1000)
        if state is None:
            lower = today - timedelta(days=14)
            candidates = self._candidates(runs, lower=lower, upper=today)
            selected = sorted(
                sorted(candidates, key=self._candidate_key, reverse=True)[:3],
                key=self._candidate_key,
            )
            jobs, _ = self.repo.enqueue_initial_backfill(
                activation_date=today.isoformat(), candidates=selected
            )
            return jobs

        activation = date.fromisoformat(state.activation_date)
        lower = max(activation, today - timedelta(days=_RECONCILE_LOOKBACK_DAYS))
        candidates = self._candidates(runs, lower=lower, upper=today)
        jobs: list[CoachJob] = []
        for candidate in sorted(candidates, key=self._candidate_key):
            if candidate.kind == "run":
                _, job, created = self.repo.enqueue_run_review(
                    run_id=candidate.run_id or "",
                    date=candidate.date,
                    occurrence_key=candidate.occurrence_key,
                )
            else:
                _, job, created = self.repo.enqueue_skip_review(
                    date=candidate.date,
                    occurrence_key=candidate.occurrence_key or "",
                    card_name=candidate.card_name or "Run",
                )
            if created:
                jobs.append(job)
        return jobs

    def _candidates(
        self, runs, *, lower: date, upper: date
    ) -> list[InitialReviewCandidate]:
        projections: dict[str, TrainingTodayResponse] = {}

        def cards_for(day_iso: str) -> TrainingTodayResponse:
            if day_iso not in projections:
                projections[day_iso] = self.gateway.training_today(day_iso)
            return projections[day_iso]

        candidates: list[InitialReviewCandidate] = []
        seen_runs: set[str] = set()
        for run in runs:
            run_date = date.fromisoformat(run.session_date)
            if lower <= run_date <= upper and run.id not in seen_runs:
                seen_runs.add(run.id)
                occurrence_key = None
                # Same association policy as `read_gateway.training_card_for_run`,
                # inlined here (rather than calling it) to reuse the `cards_for`
                # memoization above across every run/day in this scan.
                for card in cards_for(run.session_date).cards:
                    activity = card.associated_activity
                    if activity is not None and activity.run_id == run.id:
                        occurrence_key = card.occurrence_key
                        break
                candidates.append(
                    InitialReviewCandidate(
                        kind="run",
                        date=run.session_date,
                        run_id=run.id,
                        occurrence_key=occurrence_key,
                    )
                )
        day = lower
        today = date.fromisoformat(self.local_today())
        while day <= upper:
            if day < today:
                for card in cards_for(day.isoformat()).cards:
                    if (
                        card.is_running
                        and card.associated_activity is None
                        and not card.run_candidates
                        and card.status != "completed"
                    ):
                        candidates.append(
                            InitialReviewCandidate(
                                kind="skip",
                                date=day.isoformat(),
                                occurrence_key=card.occurrence_key,
                                card_name=card.card.name,
                            )
                        )
            day += timedelta(days=1)
        return candidates

    @staticmethod
    def _candidate_key(candidate: InitialReviewCandidate) -> tuple[str, str, str]:
        return (
            candidate.date,
            candidate.kind,
            candidate.run_id or candidate.occurrence_key or "",
        )

    def reconcile_idle_threads(self, *, now: str | None = None) -> list[CoachJob]:
        current = datetime.fromisoformat((now or utc_now_iso()).replace("Z", "+00:00"))
        cutoff = current.astimezone(UTC) - timedelta(hours=6)
        jobs: list[CoachJob] = []
        for thread in sorted(self.repo.list_threads(), key=lambda item: item.last_activity_at):
            activity = datetime.fromisoformat(thread.last_activity_at.replace("Z", "+00:00"))
            if thread.status == "open" and activity.astimezone(UTC) <= cutoff:
                self.repo.mark_thread_closing(thread.id, updated_at=now or utc_now_iso())
                jobs.append(self.repo.enqueue_distill(thread_id=thread.id))
        return jobs
