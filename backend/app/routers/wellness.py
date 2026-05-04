"""Compatibility wrapper for wellness routes."""

from app.domains.garmin_analytics.api.biometrics import (
    get_wellness,
)
from app.domains.garmin_analytics.api.biometrics import wellness_router as router

__all__ = ["get_wellness", "router"]
