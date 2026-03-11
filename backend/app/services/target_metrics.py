"""Target metric registry service."""

from ..models import TargetMetricsResponse
from ..target_metrics import list_target_metrics


def get_target_metrics() -> TargetMetricsResponse:
    """Return the supported target metrics."""
    metrics = list_target_metrics()
    return TargetMetricsResponse(metrics=metrics, total=len(metrics))
