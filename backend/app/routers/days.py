"""Days HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..infra.contracts import DaysResponse, DaySummaryResponse
from ..infra.database import DATA_DIR, load_available_days
from ..parser import get_day_summary

router = APIRouter(prefix="/api/days", tags=["days"])


@router.get("", response_model=DaysResponse)
def list_days():
    """List available days of data."""
    days = load_available_days()
    return DaysResponse(days=days)


@router.get("/{date}", response_model=DaySummaryResponse)
def get_day(date: str):
    """Get summary for a specific ingested day."""
    days = set(load_available_days())
    if date not in days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")

    summary = get_day_summary(DATA_DIR, date)
    if "error" in summary:
        return DaySummaryResponse(
            date=date,
            total_files=0,
            file_types={},
            total_size_kb=0.0,
        )
    return DaySummaryResponse.model_validate(summary)
