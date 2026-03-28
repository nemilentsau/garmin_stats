"""Heart-rate HTTP routes."""

from fastapi import APIRouter, Query

from ..models import (
    HeartRateAnalysisResponse,
    HeartRateInsightsResponse,
    HRDistributionResponse,
)
from ..services.heart_rate import load_heart_rate_insights
from ..services.heart_rate_analysis import load_heart_rate_analysis, load_hr_distribution

router = APIRouter(prefix="/api/heart-rate", tags=["heart-rate"])


@router.get("/insights", response_model=HeartRateInsightsResponse)
def get_heart_rate_insights(
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived heart-rate insights for UI rendering."""
    return load_heart_rate_insights(date)


@router.get("/analysis", response_model=HeartRateAnalysisResponse)
def get_heart_rate_analysis():
    """Return period-level heart-rate analysis (circadian, sleeping HR, resting trend, boxplots)."""
    return load_heart_rate_analysis()


@router.get("/distribution", response_model=HRDistributionResponse)
def get_hr_distribution(
    date: str = Query(..., description="Day (YYYY-MM-DD)"),
):
    """Return heart-rate histogram for a single day."""
    return load_hr_distribution(date)
