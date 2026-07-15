"""Single-worker execution and cancellation tests."""

from __future__ import annotations

import asyncio

from app.domains.coach.application.worker import CoachWorker
from app.domains.coach.contracts import CoachJob

NOW = "2026-07-12T12:00:00Z"


def _job(job_id: str) -> CoachJob:
    return CoachJob(
        id=job_id,
        kind="chat_turn",
        dedupe_key=job_id,
        priority=0,
        status="running",
        payload={"thread_id": "thread-1"},
        attempt_count=1,
        available_at=NOW,
        started_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeRepo:
    def __init__(self, jobs: list[CoachJob]) -> None:
        self.jobs = jobs

    def claim_next_job(self, now: str):
        del now
        return self.jobs.pop(0) if self.jobs else None


class FakeJobs:
    def __init__(self) -> None:
        self.calls = 0

    def reconcile_pending(self):
        self.calls += 1
        return []

    def reconcile_idle_threads(self):
        return []


def test_worker_executes_claimed_jobs_serially_and_broadcasts():
    active = 0
    maximum = 0
    handled: list[str] = []
    broadcasts: list[tuple[str, str]] = []

    class Handlers:
        async def execute(self, job):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0)
            handled.append(job.id)
            active -= 1

        def fail_unexpected(self, job, error):
            raise AssertionError((job, error))

    async def broadcast(event, data):
        broadcasts.append((event, data))

    worker = CoachWorker(
        repo=FakeRepo([_job("one"), _job("two")]),  # type: ignore[arg-type]
        handlers=Handlers(),  # type: ignore[arg-type]
        jobs=FakeJobs(),  # type: ignore[arg-type]
        broadcast=broadcast,
        poll_interval_s=0.01,
    )

    async def exercise():
        task = asyncio.create_task(worker.run())
        while len(handled) < 2:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())

    assert handled == ["one", "two"]
    assert maximum == 1
    assert broadcasts == [("coach_updated", "one"), ("coach_updated", "two")]


def test_worker_survives_unexpected_handler_failure():
    handled: list[str] = []
    failed: list[str] = []

    class Handlers:
        async def execute(self, job):
            handled.append(job.id)
            if job.id == "one":
                raise RuntimeError("boom")

        def fail_unexpected(self, job, error):
            del error
            failed.append(job.id)

    async def exercise():
        worker = CoachWorker(
            repo=FakeRepo([_job("one"), _job("two")]),  # type: ignore[arg-type]
            handlers=Handlers(),  # type: ignore[arg-type]
            jobs=FakeJobs(),  # type: ignore[arg-type]
            broadcast=lambda event, data: asyncio.sleep(0),
            poll_interval_s=0.01,
        )
        task = asyncio.create_task(worker.run())
        while len(handled) < 2:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert handled == ["one", "two"]
    assert failed == ["one"]


def test_worker_survives_claim_and_reconcile_failures():
    """A locked-database error from reconcile or claim must not kill the loop."""
    handled: list[str] = []

    class FlakyJobs:
        def __init__(self) -> None:
            self.calls = 0

        def reconcile_pending(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("database is locked")
            return []

        def reconcile_idle_threads(self):
            return []

    class FlakyRepo:
        def __init__(self, jobs: list[CoachJob]) -> None:
            self.jobs = jobs
            self.calls = 0

        def claim_next_job(self, now: str):
            del now
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("database is locked")
            return self.jobs.pop(0) if self.jobs else None

    class Handlers:
        async def execute(self, job):
            handled.append(job.id)

        def fail_unexpected(self, job, error):
            raise AssertionError((job, error))

    async def exercise():
        worker = CoachWorker(
            repo=FlakyRepo([_job("one")]),  # type: ignore[arg-type]
            handlers=Handlers(),  # type: ignore[arg-type]
            jobs=FlakyJobs(),  # type: ignore[arg-type]
            broadcast=lambda event, data: asyncio.sleep(0),
            poll_interval_s=0.01,
            reconcile_interval_s=0,
        )
        task = asyncio.create_task(worker.run())
        while len(handled) < 1:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert handled == ["one"]


def test_worker_survives_failing_fail_path():
    """A handler failure whose own fail_unexpected also raises must not kill the loop."""
    handled: list[str] = []

    class Handlers:
        async def execute(self, job):
            handled.append(job.id)
            raise RuntimeError("boom")

        def fail_unexpected(self, job, error):
            del error
            raise ValueError(f"malformed payload for job {job.id}")

    async def exercise():
        worker = CoachWorker(
            repo=FakeRepo([_job("one"), _job("two")]),  # type: ignore[arg-type]
            handlers=Handlers(),  # type: ignore[arg-type]
            jobs=FakeJobs(),  # type: ignore[arg-type]
            broadcast=lambda event, data: asyncio.sleep(0),
            poll_interval_s=0.01,
        )
        task = asyncio.create_task(worker.run())
        while len(handled) < 2:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert handled == ["one", "two"]


def test_worker_cancellation_propagates_from_running_handler():
    started = asyncio.Event()

    class Handlers:
        async def execute(self, job):
            del job
            started.set()
            await asyncio.Event().wait()

        def fail_unexpected(self, job, error):
            raise AssertionError((job, error))

    async def exercise():
        worker = CoachWorker(
            repo=FakeRepo([_job("one")]),  # type: ignore[arg-type]
            handlers=Handlers(),  # type: ignore[arg-type]
            jobs=FakeJobs(),  # type: ignore[arg-type]
            broadcast=lambda event, data: asyncio.sleep(0),
        )
        task = asyncio.create_task(worker.run())
        await started.wait()
        task.cancel()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)

    asyncio.run(exercise())
