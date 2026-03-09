"""Daily aggregates HTTP routes."""

from fastapi import APIRouter

from ..infra.database import load_daily_metrics
from ..models import DailyAggregatesResponse
from ..services.period_windows import load_windowed_period_summary

router = APIRouter(prefix="/api/daily-aggregates", tags=["daily-aggregates"])


@router.get("", response_model=DailyAggregatesResponse)
def get_daily_agg():
    """Get per-day aggregate stats for all metrics, plus windowed period summaries."""
    metrics = load_daily_metrics()
    days = [m.date for m in metrics]
    return DailyAggregatesResponse(
        days=days,
        daily=metrics,
        period_windows=load_windowed_period_summary(),
    )
