"""Compatibility wrapper for dashboard routes."""

from app.domains.garmin_analytics.api.overview import (
    get_dashboard_overview,
    router,
)

__all__ = ["get_dashboard_overview", "router"]
