"""Skin temperature HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..database import load_skin_temp
from ..models import SkinTempResponse
from ..stats import flatten_skin_temp

router = APIRouter(prefix="/api/skin-temp", tags=["skin-temp"])


@router.get("", response_model=SkinTempResponse)
def get_skin_temp(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get skin temperature data."""
    days = load_skin_temp(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_skin_temp(days)
