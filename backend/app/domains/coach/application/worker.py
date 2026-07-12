"""One process-local async consumer for the durable coach queue."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.handlers import CoachHandlers
from app.domains.coach.application.jobs import CoachJobs
from app.domains.coach.time import utc_now_iso

Broadcast = Callable[[str, str], Awaitable[None]]


class CoachWorker:
    def __init__(
        self,
        *,
        repo: SqliteCoachRepository,
        handlers: CoachHandlers,
        jobs: CoachJobs,
        broadcast: Broadcast,
        poll_interval_s: float = 2,
        reconcile_interval_s: float = 300,
    ) -> None:
        self.repo = repo
        self.handlers = handlers
        self.jobs = jobs
        self.broadcast = broadcast
        self.poll_interval_s = poll_interval_s
        self.reconcile_interval_s = reconcile_interval_s

    async def run(self) -> None:
        """Claim and execute exactly one job at a time until cancelled."""
        next_reconcile = time.monotonic() + self.reconcile_interval_s
        while True:
            if time.monotonic() >= next_reconcile:
                await asyncio.to_thread(self.jobs.reconcile_pending)
                await asyncio.to_thread(self.jobs.reconcile_idle_threads)
                next_reconcile = time.monotonic() + self.reconcile_interval_s
            job = await asyncio.to_thread(self.repo.claim_next_job, utc_now_iso())
            if job is None:
                await asyncio.sleep(self.poll_interval_s)
                continue
            try:
                await self.handlers.execute(job)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await asyncio.to_thread(self.handlers.fail_unexpected, job, error)
            finally:
                await self.broadcast("coach_updated", job.id)
