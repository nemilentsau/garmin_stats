"""Compatibility wrapper for dashboard overview use case."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.overview import (
    get_dashboard_overview,
)
from app.models import DashboardOverviewResponse


def load_dashboard_overview() -> DashboardOverviewResponse:
    """Load readiness score and cross-domain correlations."""
    return get_dashboard_overview(build_container().garmin_biometrics_repo)
