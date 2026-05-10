"""Application lifespan wiring and startup ingest behavior."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..domains.experiments.application.analysis_cache import refresh_active_experiments
from ..domains.garmin_sync.runtime import run_startup_ingest_if_needed
from ..domains.garmin_sync.watcher import watch_data_directory
from ..infra.database import DATA_DIR, init_db
from ..infra.events import heartbeat_loop
from .container import build_container

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _task_done_callback(task: asyncio.Task) -> None:
    """Log exceptions from background tasks instead of swallowing them."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        log.error("Background task %s failed: %s", task.get_name(), exc, exc_info=exc)


def _refresh_active_experiment_analyses() -> int:
    """Refresh experiment analyses after successful Garmin ingest."""
    return refresh_active_experiments(build_container().experiments_repo)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, auto-ingest if empty, start file watcher."""
    init_db()
    run_startup_ingest_if_needed(DATA_DIR)

    watcher_task = asyncio.create_task(
        watch_data_directory(
            DATA_DIR,
            refresh_after_ingest=_refresh_active_experiment_analyses,
        ),
        name="file-watcher",
    )
    watcher_task.add_done_callback(_task_done_callback)
    heartbeat_task = asyncio.create_task(heartbeat_loop(), name="sse-heartbeat")
    heartbeat_task.add_done_callback(_task_done_callback)
    yield
    watcher_task.cancel()
    heartbeat_task.cancel()
