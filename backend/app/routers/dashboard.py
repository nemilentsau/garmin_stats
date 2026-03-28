"""Dashboard overview HTTP routes."""

from fastapi import APIRouter

from ..models import DashboardOverviewResponse
from ..services.dashboard import load_dashboard_overview

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOverviewResponse)
def get_dashboard_overview():
    """Return readiness score and cross-domain correlations."""
    return load_dashboard_overview()
