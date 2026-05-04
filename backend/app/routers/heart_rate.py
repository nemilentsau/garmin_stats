"""Compatibility wrapper for heart-rate routes."""

from app.domains.garmin_analytics.api.insights import (
    get_heart_rate_analysis,
    get_heart_rate_insights,
    get_hr_distribution,
)
from app.domains.garmin_analytics.api.insights import (
    heart_rate_router as router,
)

__all__ = [
    "get_heart_rate_analysis",
    "get_heart_rate_insights",
    "get_hr_distribution",
    "router",
]
