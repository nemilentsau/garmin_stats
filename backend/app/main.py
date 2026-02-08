"""
Garmin Stats API - FastAPI backend for health data analysis.
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .parser import (
    get_available_days,
    get_day_summary,
    parse_wellness,
    parse_sleep,
    parse_hrv,
    parse_skin_temp,
    parse_all_days,
)
from .stats import (
    flatten_wellness,
    flatten_sleep,
    flatten_hrv,
    flatten_skin_temp,
    compute_daily_aggregates,
)
from .models import (
    WellnessResponse,
    SleepResponse,
    HrvResponse,
    SkinTempResponse,
    DailyAggregatesResponse,
    DaySummaryResponse,
    DaysResponse,
)

# Data directory - relative to project root
DATA_DIR = Path(__file__).parent.parent.parent / "data"

app = FastAPI(
    title="Garmin Stats API",
    description="API for analyzing Garmin Epix Gen 2 health data",
    version="0.1.0",
    separate_input_output_schemas=True,
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


@app.get("/api/days", response_model=DaysResponse)
def list_days():
    """List available days of data."""
    days = get_available_days(DATA_DIR)
    return DaysResponse(days=days, total=len(days))


@app.get("/api/days/{date}", response_model=DaySummaryResponse)
def get_day(date: str):
    """Get summary for a specific day."""
    summary = get_day_summary(DATA_DIR, date)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@app.get("/api/wellness", response_model=WellnessResponse)
def get_wellness(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get wellness data (HR, stress, SpO2, respiration, activity)."""
    days = parse_wellness(DATA_DIR, date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_wellness(days)


@app.get("/api/sleep", response_model=SleepResponse)
def get_sleep(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get sleep data (stages, assessment scores)."""
    days = parse_sleep(DATA_DIR, date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_sleep(days)


@app.get("/api/hrv", response_model=HrvResponse)
def get_hrv(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get HRV data (values, summaries)."""
    days = parse_hrv(DATA_DIR, date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_hrv(days)


@app.get("/api/daily-aggregates", response_model=DailyAggregatesResponse)
def get_daily_agg():
    """Get per-day aggregate stats for all metrics."""
    days = parse_all_days(DATA_DIR)
    return compute_daily_aggregates(days)


@app.get("/api/skin-temp", response_model=SkinTempResponse)
def get_skin_temp(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get skin temperature data."""
    days = parse_skin_temp(DATA_DIR, date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_skin_temp(days)
