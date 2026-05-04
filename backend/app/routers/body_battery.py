"""Compatibility wrapper for body battery routes."""

from app.domains.garmin_analytics.api.insights import (
    body_battery_router as router,
)
from app.domains.garmin_analytics.api.insights import (
    get_body_battery_analysis,
)

__all__ = ["get_body_battery_analysis", "router"]
