"""Today projection HTTP routes."""

from fastapi import APIRouter, Query

from ..models import CardLog, TodayCardLogUpdateRequest, TodayResponse
from ..services.today import get_today, upsert_today_card_log

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Return compiled cards for a single day."""
    return get_today(date)


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    """Create or replace the log for a single card occurrence."""
    return upsert_today_card_log(date, occurrence_key, request)
