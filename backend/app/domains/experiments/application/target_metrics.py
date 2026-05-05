"""Target metric registry service."""

from app.domains.experiments.domain.target_metrics import list_target_metrics
from app.models import TargetMetricsResponse


def get_target_metrics() -> TargetMetricsResponse:
    """Return the supported target metrics."""
    metrics = list_target_metrics()
    return TargetMetricsResponse(metrics=metrics)
