"""Compatibility wrapper for sleep routes."""

from app.domains.garmin_analytics.api.biometrics import (
    get_sleep,
    get_sleep_analysis,
)
from app.domains.garmin_analytics.api.biometrics import sleep_router as router

__all__ = ["get_sleep", "get_sleep_analysis", "router"]
