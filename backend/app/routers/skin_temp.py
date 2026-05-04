"""Compatibility wrapper for skin temperature routes."""

from app.domains.garmin_analytics.api.biometrics import (
    get_skin_temp,
)
from app.domains.garmin_analytics.api.biometrics import skin_temp_router as router

__all__ = ["get_skin_temp", "router"]
