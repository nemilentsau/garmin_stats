"""Dashboard overview routes for Garmin analytics."""

from fastapi import APIRouter

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.overview import (
    get_dashboard_overview as load_dashboard_overview,
)
from app.models import DashboardOverviewResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOverviewResponse)
def get_dashboard_overview():
    """Return readiness score and cross-domain correlations."""
    return load_dashboard_overview(build_container().garmin_biometrics_repo)
