"""Compatibility wrapper for stress routes."""

from app.domains.garmin_analytics.api.insights import (
    get_stress_analysis,
)
from app.domains.garmin_analytics.api.insights import (
    stress_router as router,
)

__all__ = ["get_stress_analysis", "router"]
