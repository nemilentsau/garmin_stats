"""Domain-local today routes."""

from fastapi import APIRouter, Query

from app.models import CardLog, CardLogRangeResponse, TodayCardLogUpdateRequest, TodayResponse

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    from app.routers import today as compat_today

    return compat_today.get_today(date)


@router.get("/card-logs", response_model=CardLogRangeResponse)
def get_today_card_logs(start_date: str = Query(...), end_date: str = Query(...)):
    from app.routers import today as compat_today

    return compat_today.get_card_log_range(start_date, end_date)


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    from app.routers import today as compat_today

    return compat_today.upsert_today_card_log(date, occurrence_key, request)
