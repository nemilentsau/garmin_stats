"""Stress HTTP routes."""

from fastapi import APIRouter

from ..models import StressAnalysisResponse
from ..services.stress_analysis import load_stress_analysis

router = APIRouter(prefix="/api/stress", tags=["stress"])


@router.get("/analysis", response_model=StressAnalysisResponse)
def get_stress_analysis():
    """Return period-level stress analysis (avg trend, weekly boxplots)."""
    return load_stress_analysis()
