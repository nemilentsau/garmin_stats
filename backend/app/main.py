"""
Garmin Stats API - FastAPI backend for health data analysis.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .infra.database import DATA_DIR, check_ingest_status, ingest_all, init_db
from .infra.watcher import extract_existing_archives, heartbeat_loop, watch_data_directory
from .routers.assistant import router as assistant_router
from .routers.assistant_artifacts import router as assistant_artifacts_router
from .routers.body_battery import router as body_battery_router
from .routers.cards import router as cards_router
from .routers.checkins import router as checkins_router
from .routers.daily_aggregates import router as daily_aggregates_router
from .routers.dashboard import router as dashboard_router
from .routers.days import router as days_router
from .routers.events import router as events_router
from .routers.experiments import router as experiments_router
from .routers.heart_rate import router as heart_rate_router
from .routers.hrv import router as hrv_router
from .routers.ingest import router as ingest_router
from .routers.notes import router as notes_router
from .routers.profile import router as profile_router
from .routers.programs import router as programs_router
from .routers.routines import router as routines_router
from .routers.skin_temp import router as skin_temp_router
from .routers.sleep import router as sleep_router
from .routers.stress import router as stress_router
from .routers.target_metrics import router as target_metrics_router
from .routers.today import router as today_router
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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5180",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5180",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_api_response_caching(request: Request, call_next):
    """Mark API responses as non-cacheable unless a route sets its own policy."""
    response = await call_next(request)
    if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

app.include_router(ingest_router)
app.include_router(dashboard_router)
app.include_router(days_router)
app.include_router(wellness_router)
app.include_router(sleep_router)
app.include_router(daily_aggregates_router)
app.include_router(skin_temp_router)
app.include_router(heart_rate_router)
app.include_router(hrv_router)
app.include_router(stress_router)
app.include_router(body_battery_router)
app.include_router(events_router)
app.include_router(assistant_router)
app.include_router(assistant_artifacts_router)
app.include_router(cards_router)
app.include_router(profile_router)
app.include_router(routines_router)
app.include_router(checkins_router)
app.include_router(notes_router)
app.include_router(experiments_router)
app.include_router(target_metrics_router)
app.include_router(programs_router)
app.include_router(today_router)


@app.get("/")
def root():
    """API root - health check."""
    return {
        "status": "ok",
        "message": "Garmin Stats API",
        "data_dir": str(DATA_DIR),
        "data_exists": DATA_DIR.exists(),
    }
