"""
Garmin Stats API - FastAPI backend for health data analysis.
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .parser import (
    get_available_days,
    get_day_summary,
    get_overview_stats,
    get_daily_aggregates,
    parse_wellness_data,
    parse_sleep_data,
    parse_hrv_data,
    parse_skin_temp_data,
)

# Data directory - relative to project root
DATA_DIR = Path(__file__).parent.parent.parent / "data"

app = FastAPI(
    title="Garmin Stats API",
    description="API for analyzing Garmin Epix Gen 2 health data",
    version="0.1.0",
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


@app.get("/api/days")
def list_days():
    """List available days of data."""
    days = get_available_days(DATA_DIR)
    return {
        "days": days,
        "total": len(days),
    }


@app.get("/api/days/{date}")
def get_day(date: str):
    """Get summary for a specific day."""
    summary = get_day_summary(DATA_DIR, date)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@app.get("/api/overview")
def get_overview():
    """Get overview statistics across all data."""
    return get_overview_stats(DATA_DIR)


@app.get("/api/wellness")
def get_wellness(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get wellness data (HR, stress, SpO2, respiration, activity)."""
    data = parse_wellness_data(DATA_DIR, date)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/api/sleep")
def get_sleep(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get sleep data (stages, assessment scores)."""
    data = parse_sleep_data(DATA_DIR, date)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/api/hrv")
def get_hrv(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get HRV data (values, summaries)."""
    data = parse_hrv_data(DATA_DIR, date)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/api/daily-aggregates")
def get_daily_agg():
    """Get per-day aggregate stats for all metrics."""
    return get_daily_aggregates(DATA_DIR)


@app.get("/api/skin-temp")
def get_skin_temp(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get skin temperature data."""
    data = parse_skin_temp_data(DATA_DIR, date)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data
