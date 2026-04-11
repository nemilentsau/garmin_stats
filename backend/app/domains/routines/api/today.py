"""Domain-local today routes."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.routines.application.today import (
    get_card_log_range as _get_card_log_range,
)
from app.domains.routines.application.today import (
    get_today as _get_today,
)
from app.domains.routines.application.today import (
    upsert_today_card_log as _upsert_today_card_log,
)
from app.models import (
    CardLog,
    CardLogRangeResponse,
    TodayCardLogUpdateRequest,
    TodayResponse,
)

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Return compiled cards for a single day."""
    return _get_today(build_container().routines_repo, date=date)


@router.get("/card-logs", response_model=CardLogRangeResponse)
def get_card_logs_range(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD, inclusive)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD, inclusive)"),
):
    """Return completion statuses for all card occurrences in a date range."""
    repo = build_container().routines_repo
    return _get_card_log_range(repo, start_date=start_date, end_date=end_date)


@router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    """Create or replace the log for a single card occurrence."""
    container = build_container()
    return _upsert_today_card_log(
        container.routines_repo,
        date=date,
        occurrence_key=occurrence_key,
        request=request,
        observer=container.experiment_exposure_sync,
    )
