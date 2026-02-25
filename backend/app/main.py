"""
Garmin Stats API - FastAPI backend for health data analysis.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .database import (
    DATA_DIR,
    check_ingest_status,
    ingest_all,
    init_db,
    is_db_empty,
    load_available_days,
    load_daily_metrics,
    load_hrv,
    load_period_summary,
    load_skin_temp,
    load_sleep,
    load_wellness,
)
from .events import event_bus
from .models import (
    DailyAggregatesResponse,
    DaysResponse,
    DaySummaryResponse,
    HrvResponse,
    IngestResult,
    IngestStatus,
    SkinTempResponse,
    SleepResponse,
    WellnessResponse,
)
from .parser import get_day_summary
from .stats import (
    flatten_hrv,
    flatten_skin_temp,
    flatten_sleep,
    flatten_wellness,
)
from .watcher import heartbeat_loop, watch_data_directory

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


@app.get("/")
def root():
    """API root - health check."""
    return {
        "status": "ok",
        "message": "Garmin Stats API",
        "data_dir": str(DATA_DIR),
        "data_exists": DATA_DIR.exists(),
    }


# ---------------------------------------------------------------------------
# Ingest endpoints
# ---------------------------------------------------------------------------

@app.post("/api/ingest", response_model=IngestResult)
def trigger_ingest():
    """Re-ingest all FIT files into the database."""
    try:
        return ingest_all(DATA_DIR)
    except RuntimeError as err:
        raise HTTPException(
            status_code=409, detail="Ingest already in progress",
        ) from err


@app.get("/api/ingest/status", response_model=IngestStatus)
def get_ingest_status():
    """Check whether new data needs ingesting."""
    return check_ingest_status(DATA_DIR)


# ---------------------------------------------------------------------------
# Data endpoints (read from DB)
# ---------------------------------------------------------------------------

@app.get("/api/days", response_model=DaysResponse)
def list_days():
    """List available days of data."""
    days = load_available_days()
    return DaysResponse(days=days, total=len(days))


@app.get("/api/days/{date}", response_model=DaySummaryResponse)
def get_day(date: str):
    """Get summary for a specific day (filesystem-based)."""
    summary = get_day_summary(DATA_DIR, date)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@app.get("/api/wellness", response_model=WellnessResponse)
def get_wellness(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get wellness data (HR, stress, SpO2, respiration, activity)."""
    days = load_wellness(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_wellness(days)


@app.get("/api/sleep", response_model=SleepResponse)
def get_sleep(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get sleep data (stages, assessment scores)."""
    days = load_sleep(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_sleep(days)


@app.get("/api/hrv", response_model=HrvResponse)
def get_hrv(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get HRV data (values, summaries)."""
    days = load_hrv(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_hrv(days)


@app.get("/api/daily-aggregates", response_model=DailyAggregatesResponse)
def get_daily_agg():
    """Get per-day aggregate stats for all metrics, plus period summary."""
    metrics = load_daily_metrics()
    days = [m.date for m in metrics]
    return DailyAggregatesResponse(days=days, daily=metrics, period=load_period_summary())


@app.get("/api/skin-temp", response_model=SkinTempResponse)
def get_skin_temp(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get skin temperature data."""
    days = load_skin_temp(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_skin_temp(days)


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@app.get("/api/events")
async def sse_events(request: Request):
    """Server-Sent Events stream for real-time data updates."""
    queue = event_bus.subscribe()

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except TimeoutError:
                    continue
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
