"""Compatibility wrapper for daily aggregate routes."""

from app.domains.garmin_analytics.api.biometrics import (
    daily_aggregates_router as router,
)
from app.domains.garmin_analytics.api.biometrics import (
    get_daily_agg,
)

__all__ = ["get_daily_agg", "router"]
