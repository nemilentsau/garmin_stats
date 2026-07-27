"""Tests for explicit Coach enqueue and idle-thread lifecycle policy."""

from __future__ import annotations

import sqlite3
from typing import cast

import pytest

import app.domains.coach.adapters as coach_adapters
from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.jobs import CoachJobs
from app.domains.coach.contracts import CoachThread
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.training.contracts import TrainingTodayResponse

NOW = "2026-07-12T12:00:00Z"


class JobsGateway:
    def run_detail(self, run_id: str):
        from tests.domains.coach.test_coach_context import _detail

        detail = _detail()
        return detail.model_copy(
            update={"session": detail.session.model_copy(update={"id": run_id})}
        )

    def training_today(self, target: str):
        return TrainingTodayResponse(date=target, cards=[])


def _jobs(repo: SqliteCoachRepository, gateway: JobsGateway) -> CoachJobs:
    return CoachJobs(repo=repo, gateway=cast(CoachReadGateway, gateway))


def test_manual_review_returns_existing_review_without_duplicate():
    repo = SqliteCoachRepository()
    jobs = _jobs(repo, JobsGateway())

    first = jobs.enqueue_run_review("run-1")
    second = jobs.enqueue_run_review("run-1")

    assert first.review is not None and second.review is not None
    assert first.review.id == second.review.id
    assert first.created is True
    assert second.created is False
    assert repo.queued_count() == 1


def test_coach_jobs_exposes_no_automatic_review_reconciliation():
    jobs = _jobs(SqliteCoachRepository(), JobsGateway())

    assert not hasattr(jobs, "reconcile_pending")


def _open_thread(repo: SqliteCoachRepository, thread_id: str = "thread-1") -> None:
    repo.insert_thread(
        CoachThread(
            id=thread_id,
            title="Recovery question",
            status="open",
            created_at=NOW,
            last_activity_at=NOW,
        )
    )


def test_close_thread_job_insert_failure_rolls_back_to_open_and_can_retry(monkeypatch):
    repo = SqliteCoachRepository()
    _open_thread(repo)
    jobs = _jobs(repo, JobsGateway())

    save_job = coach_adapters._save_job

    def fail_job_insert(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(coach_adapters, "_save_job", fail_job_insert)
    with pytest.raises(sqlite3.OperationalError):
        jobs.close_thread("thread-1")
    assert repo.thread("thread-1").status == "open"  # type: ignore[union-attr]

    monkeypatch.setattr(coach_adapters, "_save_job", save_job)
    queued = jobs.close_thread("thread-1")

    assert queued.payload["thread_id"] == "thread-1"
    assert queued.status == "queued"
    assert repo.thread("thread-1").status == "closing"  # type: ignore[union-attr]


def test_retry_close_requeues_a_distill_job_failed_by_stale_recovery():
    repo = SqliteCoachRepository()
    _open_thread(repo)
    jobs = _jobs(repo, JobsGateway())
    job = jobs.close_thread("thread-1")
    assert repo.claim_next_job("9999-01-01T00:00:00Z") is not None
    repo.recover_stale_jobs(cutoff="9999-01-01T00:00:00Z", max_attempts=1)

    retried = jobs.retry_close("thread-1")

    assert retried.id == job.id
    assert retried.status == "queued"
    assert retried.attempt_count == 0
    assert repo.thread("thread-1").status == "closing"  # type: ignore[union-attr]


def test_idle_thread_boundary_queues_distill_and_just_under_stays_open():
    repo = SqliteCoachRepository()
    for thread_id, last_activity in (
        ("idle", "2026-07-12T06:00:00Z"),
        ("active", "2026-07-12T06:00:01Z"),
    ):
        repo.insert_thread(
            CoachThread(
                id=thread_id,
                title=thread_id,
                status="open",
                created_at=NOW,
                last_activity_at=last_activity,
            )
        )
    jobs = _jobs(repo, JobsGateway())

    queued = jobs.reconcile_idle_threads(now=NOW)

    assert [job.payload["thread_id"] for job in queued] == ["idle"]
    assert repo.thread("idle").status == "closing"  # type: ignore[union-attr]
    assert repo.thread("active").status == "open"  # type: ignore[union-attr]
