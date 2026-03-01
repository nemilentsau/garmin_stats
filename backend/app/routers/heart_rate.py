"""Heart-rate HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..models import HeartRateInsightsResponse
from ..services.heart_rate import load_heart_rate_insights

router = APIRouter(prefix="/api/heart-rate", tags=["heart-rate"])


@router.get("/insights", response_model=HeartRateInsightsResponse)
def get_heart_rate_insights(
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived heart-rate insights for UI rendering."""
    try:
        return load_heart_rate_insights(date)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
