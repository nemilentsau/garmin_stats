"""
Garmin Stats API - FastAPI backend for health data analysis.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .infra.database import DATA_DIR, ingest_all, init_db, is_db_empty
from .infra.watcher import heartbeat_loop, watch_data_directory
from .routers.daily_aggregates import router as daily_aggregates_router
from .routers.dashboard import router as dashboard_router
from .routers.days import router as days_router
from .routers.events import router as events_router
from .routers.heart_rate import router as heart_rate_router
from .routers.hrv import router as hrv_router
from .routers.ingest import router as ingest_router
from .routers.skin_temp import router as skin_temp_router
from .routers.sleep import router as sleep_router
from .routers.wellness import router as wellness_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _task_done_callback(task: asyncio.Task) -> None:
    """Log exceptions from background tasks instead of swallowing them."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        log.error("Background task %s failed: %s", task.get_name(), exc, exc_info=exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, auto-ingest if empty, start file watcher."""
    init_db()
    if is_db_empty():
        log.info("DB empty — running initial ingest")
        result = ingest_all(DATA_DIR)
        log.info(
            "Initial ingest complete: %d days in %d ms",
            result.days_ingested, result.duration_ms,
        )

    watcher_task = asyncio.create_task(watch_data_directory(DATA_DIR), name="file-watcher")
    watcher_task.add_done_callback(_task_done_callback)
    heartbeat_task = asyncio.create_task(heartbeat_loop(), name="sse-heartbeat")
    heartbeat_task.add_done_callback(_task_done_callback)
    yield
    watcher_task.cancel()
    heartbeat_task.cancel()


app = FastAPI(
    title="Garmin Stats API",
    description="API for analyzing Garmin Epix Gen 2 health data",
    version="0.1.0",
    separate_input_output_schemas=True,
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(dashboard_router)
app.include_router(days_router)
app.include_router(wellness_router)
app.include_router(sleep_router)
app.include_router(daily_aggregates_router)
app.include_router(skin_temp_router)
app.include_router(heart_rate_router)
app.include_router(hrv_router)
app.include_router(events_router)


@app.get("/")
def root():
    """API root - health check."""
    return {
        "status": "ok",
        "message": "Garmin Stats API",
        "data_dir": str(DATA_DIR),
        "data_exists": DATA_DIR.exists(),
    }
