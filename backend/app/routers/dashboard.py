"""Dashboard overview HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..models import DashboardOverviewResponse
from ..services.dashboard import load_dashboard_overview

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOverviewResponse)
def get_dashboard_overview():
    """Return readiness score and cross-domain correlations."""
    try:
        return load_dashboard_overview()
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
