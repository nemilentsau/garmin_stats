"""Compatibility wrapper for HRV routes."""

from app.domains.garmin_analytics.api.biometrics import (
    get_hrv,
    get_hrv_analysis,
    get_hrv_insights,
)
from app.domains.garmin_analytics.api.biometrics import hrv_router as router

__all__ = ["get_hrv", "get_hrv_analysis", "get_hrv_insights", "router"]
