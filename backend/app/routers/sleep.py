"""Sleep HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..infra.database import load_sleep
from ..models import SleepAnalysisResponse, SleepResponse
from ..services.sleep_analysis import load_sleep_analysis
from ..stats import flatten_sleep

router = APIRouter(prefix="/api/sleep", tags=["sleep"])


@router.get("", response_model=SleepResponse)
def get_sleep(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Get sleep data (stages, assessment scores)."""
    days = load_sleep(date)
    if date and not days:
        raise HTTPException(status_code=404, detail=f"Day {date} not found")
    return flatten_sleep(days)


@router.get("/analysis", response_model=SleepAnalysisResponse)
def get_sleep_analysis():
    """Return period-level sleep analysis (score trend, weekly boxplots)."""
    return load_sleep_analysis()
