"""Process runtime composition for startup and background tasks."""

from __future__ import annotations

import asyncio
import logging

from app.bootstrap.container import AppContainer
from app.domains.experiments.application.analysis_cache import refresh_active_experiments
from app.domains.garmin_sync.infra.runtime import run_startup_ingest_if_needed
from app.infra.events import heartbeat_loop

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
        """Run startup reconciliation and start background tasks."""
        run_startup_ingest_if_needed(self._container.garmin_sync)

        watcher_task = asyncio.create_task(
            self._container.garmin_sync_watcher.watch(
                refresh_after_ingest=self._refresh_active_experiment_analyses,
            ),
            name="file-watcher",
        )
        watcher_task.add_done_callback(_task_done_callback)

        heartbeat_task = asyncio.create_task(heartbeat_loop(), name="sse-heartbeat")
        heartbeat_task.add_done_callback(_task_done_callback)

        self._tasks = [watcher_task, heartbeat_task]

    def stop(self) -> None:
        for task in self._tasks:
            task.cancel()

    def _refresh_active_experiment_analyses(self) -> int:
        return refresh_active_experiments(self._container.experiments_repo)


def build_process_runtime(container: AppContainer) -> ProcessRuntime:
    return ProcessRuntime(container)
