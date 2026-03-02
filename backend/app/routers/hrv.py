"""HRV HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..database import load_hrv
from ..models import HrvInsightsResponse, HrvResponse
from ..services.hrv import load_hrv_insights
from ..stats import flatten_hrv

router = APIRouter(prefix="/api/hrv", tags=["hrv"])


@router.get("", response_model=HrvResponse)
def get_hrv(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get HRV data (values, summaries)."""
    days = load_hrv(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_hrv(days)


@router.get("/insights", response_model=HrvInsightsResponse)
def get_hrv_insights(
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived HRV insights for UI rendering."""
    try:
        return load_hrv_insights(date)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
