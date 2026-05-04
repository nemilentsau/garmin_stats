"""Compatibility wrapper for Garmin analytics heart-rate insights."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.heart_rate import (
    _build_insights,
    _compute_recovery,
    _compute_zone_minutes,
    _estimate_default_interval_minutes,
    _zone_for_value,
)
from app.domains.garmin_analytics.application.heart_rate import (
    load_heart_rate_insights as _load_heart_rate_insights,
)
from app.models import HeartRateInsightsResponse


def load_heart_rate_insights(date: str | None = None) -> HeartRateInsightsResponse:
    return _load_heart_rate_insights(
        build_container().garmin_biometrics_repo,
        date,
    )


__all__ = [
    "_build_insights",
    "_compute_recovery",
    "_compute_zone_minutes",
    "_estimate_default_interval_minutes",
    "_zone_for_value",
    "load_heart_rate_insights",
]
