"""Daily check-in HTTP routes."""

from fastapi import APIRouter, Query

from ..models import DailyCheckIn, DailyCheckInsResponse
from ..services.checkins import create_checkin, list_checkins

router = APIRouter(prefix="/api/checkins", tags=["checkins"])


@router.get("", response_model=DailyCheckInsResponse)
def get_checkins(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Return daily check-ins."""
    return list_checkins(date=date)


@router.post("", response_model=DailyCheckIn)
def post_checkin(checkin: DailyCheckIn):
    """Create or replace a daily check-in."""
    return create_checkin(checkin)
