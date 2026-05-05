"""Target metric registry HTTP routes."""

from fastapi import APIRouter

from app.domains.experiments.application.target_metrics import get_target_metrics
from app.models import TargetMetricsResponse

router = APIRouter(prefix="/api/target-metrics", tags=["target-metrics"])


@router.get("", response_model=TargetMetricsResponse)
def list_target_metrics_route():
    """Return the supported target metric registry."""
    return get_target_metrics()
