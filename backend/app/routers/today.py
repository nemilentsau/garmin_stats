"""Today projection HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    CardLog,
    CardOverride,
    TodayCardLogUpdateRequest,
    TodayCardOverrideCreateRequest,
    TodayResponse,
)
from ..services.today import (
    create_today_override,
    get_today,
    hide_today_card,
    upsert_today_card_log,
)

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Return compiled cards for a single day."""
    return get_today(date)


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    """Create or replace the log for a single card occurrence."""
    return upsert_today_card_log(date, occurrence_key, request)


@router.post("/{date}/cards", response_model=CardOverride)
def post_today_override(date: str, request: TodayCardOverrideCreateRequest):
    """Create a date-specific add/hide/replace override."""
    try:
        return create_today_override(date, request)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete("/{date}/cards/{occurrence_key}", response_model=CardOverride)
def delete_today_card(date: str, occurrence_key: str):
    """Hide a single card occurrence for the selected date."""
    return hide_today_card(date, occurrence_key)
