"""Daily aggregates HTTP routes."""

from fastapi import APIRouter

from ..database import load_daily_metrics, load_period_summary
from ..models import DailyAggregatesResponse

router = APIRouter(prefix="/api/daily-aggregates", tags=["daily-aggregates"])


@router.get("", response_model=DailyAggregatesResponse)
def get_daily_agg():
    """Get per-day aggregate stats for all metrics, plus period summary."""
    metrics = load_daily_metrics()
    days = [m.date for m in metrics]
    return DailyAggregatesResponse(days=days, daily=metrics, period=load_period_summary())
