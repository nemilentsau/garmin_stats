"""Process runtime composition for startup and background tasks."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.bootstrap.container import AppContainer
from app.domains.experiments.application.analysis_cache import refresh_active_experiments
from app.domains.garmin_sync.infra.runtime import run_startup_ingest_if_needed
from app.realtime.events import heartbeat_loop

log = logging.getLogger(__name__)


def _task_done_callback(task: asyncio.Task[None]) -> None:
    """Log exceptions from background tasks instead of swallowing them."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        log.error("Background task %s failed: %s", task.get_name(), exc, exc_info=exc)


class ProcessRuntime:
    """Own process startup hooks and long-running background tasks."""

    def __init__(self, container: AppContainer) -> None:
        self._container = container
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        run_startup_ingest_if_needed(self._container.garmin_sync)

        tasks: list[asyncio.Task[None]] = []
        if self._container.config.coach_worker_enabled:
            # A single-process deployment cannot have a legitimately running
            # job at startup; recover everything still marked running.
            try:
                self._container.coach_repo.recover_stale_jobs(
                    cutoff=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    max_attempts=3,
                )
            except Exception:
                log.exception("Coach stale-job recovery failed; startup will continue")
            try:
                self._container.coach_jobs.reconcile_pending()
            except Exception:
                log.exception("Coach pending-job reconciliation failed; startup will continue")
            coach_task = asyncio.create_task(
                self._container.coach_worker.run(), name="coach-worker"
            )
            coach_task.add_done_callback(_task_done_callback)
            tasks.append(coach_task)

        watcher_task = asyncio.create_task(
            self._container.garmin_sync_watcher.watch(
                refresh_after_ingest=self._refresh_after_ingest,
            ),
            name="file-watcher",
        )
        watcher_task.add_done_callback(_task_done_callback)

        heartbeat_task = asyncio.create_task(heartbeat_loop(), name="sse-heartbeat")
        heartbeat_task.add_done_callback(_task_done_callback)

        self._tasks = [*tasks, watcher_task, heartbeat_task]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _refresh_active_experiment_analyses(self) -> int:
        return refresh_active_experiments(
            self._container.experiments_repo,
            self._container.experiments_read_source,
        )

    def _refresh_after_ingest(self) -> int:
        refreshed = self._refresh_active_experiment_analyses()
        if self._container.config.coach_worker_enabled:
            refreshed += len(self._container.coach_jobs.reconcile_pending())
        return refreshed
