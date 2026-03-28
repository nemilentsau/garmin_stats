"""Today projection HTTP routes."""

from fastapi import APIRouter, Query

from ..infra.database import load_card_logs_range
from ..models import (
    CardLog,
    CardLogRangeResponse,
    CardLogStatusEntry,
    TodayCardLogUpdateRequest,
    TodayResponse,
)
from ..services.today import get_today, upsert_today_card_log

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Return compiled cards for a single day."""
    return get_today(date)


@router.get("/card-logs", response_model=CardLogRangeResponse)
def get_card_logs_range(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD, inclusive)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD, inclusive)"),
):
    """Return completion statuses for all card occurrences in a date range."""
    logs = load_card_logs_range(start_date, end_date)
    entries = [
        CardLogStatusEntry(occurrence_key=log.occurrence_key, status=log.status)
        for log in logs
        if log.status != "pending"
    ]
    return CardLogRangeResponse(
        start_date=start_date,
        end_date=end_date,
        entries=entries,
    )


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    """Create or replace the log for a single card occurrence."""
    return upsert_today_card_log(date, occurrence_key, request)
