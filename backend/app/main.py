"""
Garmin Stats API - FastAPI backend for health data analysis.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import (
    DATA_DIR,
    init_db,
    is_db_empty,
    ingest_all,
    check_ingest_status,
    load_daily_metrics,
    load_period_summary,
    load_wellness,
    load_sleep,
    load_hrv,
    load_skin_temp,
    load_available_days,
)
from .parser import get_day_summary
from .stats import (
    flatten_wellness,
    flatten_sleep,
    flatten_hrv,
    flatten_skin_temp,
)
from .models import (
    WellnessResponse,
    SleepResponse,
    HrvResponse,
    SkinTempResponse,
    DailyAggregatesResponse,
    DaySummaryResponse,
    DaysResponse,
    IngestResult,
    IngestStatus,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, auto-ingest if empty."""
    init_db()
    if is_db_empty():
        log.info("DB empty — running initial ingest")
        result = ingest_all(DATA_DIR)
        log.info("Initial ingest complete: %d days in %d ms", result.days_ingested, result.duration_ms)
    yield


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
    except RuntimeError:
        raise HTTPException(status_code=409, detail="Ingest already in progress")


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
