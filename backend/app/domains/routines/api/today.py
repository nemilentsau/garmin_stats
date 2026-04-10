"""Domain-local today routes."""

from functools import lru_cache

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.routines.application.today import (
    get_card_log_range,
    get_today,
    upsert_today_card_log,
)
from app.models import CardLog, CardLogRangeResponse, TodayCardLogUpdateRequest, TodayResponse

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    return get_today(_repo(), date=date)


@router.get("/card-logs", response_model=CardLogRangeResponse)
def get_today_card_logs(start_date: str = Query(...), end_date: str = Query(...)):
    return get_card_log_range(_repo(), start_date=start_date, end_date=end_date)


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    return upsert_today_card_log(
        _repo(),
        date=date,
        occurrence_key=occurrence_key,
        request=request,
    )


@lru_cache(maxsize=1)
def _repo():
    return build_container().routines_repo
