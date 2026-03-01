"""Wellness HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..database import load_wellness
from ..models import WellnessResponse
from ..stats import flatten_wellness

router = APIRouter(prefix="/api/wellness", tags=["wellness"])


@router.get("", response_model=WellnessResponse)
def get_wellness(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get wellness data (HR, stress, SpO2, respiration, activity)."""
    days = load_wellness(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_wellness(days)
