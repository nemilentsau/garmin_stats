"""Application lifespan wiring and startup ingest behavior."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..domains.garmin_sync.adapters import check_ingest_status, ingest_all
from ..infra.database import DATA_DIR, init_db
from ..infra.watcher import extract_existing_archives, heartbeat_loop, watch_data_directory

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _task_done_callback(task: asyncio.Task) -> None:
    """Log exceptions from background tasks instead of swallowing them."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        log.error("Background task %s failed: %s", task.get_name(), exc, exc_info=exc)


def _run_startup_ingest_if_needed() -> None:
    """Reconcile existing day archives and ingest when disk state changed."""
    extract_existing_archives(DATA_DIR)
    status = check_ingest_status(DATA_DIR)
    if not status.needs_ingest:
        log.info(
            "Startup data already in sync: %d days in DB, %d days on disk",
            status.days_in_db,
            status.days_on_disk,
        )
        return

    reason = "DB empty" if status.days_in_db == 0 else "Data directory changed"
    log.info("%s — running startup ingest", reason)
    result = ingest_all(DATA_DIR)
    log.info(
        "Startup ingest complete: %d days in %d ms",
        result.days_ingested,
        result.duration_ms,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, auto-ingest if empty, start file watcher."""
    init_db()
    _run_startup_ingest_if_needed()

    watcher_task = asyncio.create_task(
        watch_data_directory(DATA_DIR, ingest_all),
        name="file-watcher",
    )
    watcher_task.add_done_callback(_task_done_callback)
    heartbeat_task = asyncio.create_task(heartbeat_loop(), name="sse-heartbeat")
    heartbeat_task.add_done_callback(_task_done_callback)
    yield
    watcher_task.cancel()
    heartbeat_task.cancel()
