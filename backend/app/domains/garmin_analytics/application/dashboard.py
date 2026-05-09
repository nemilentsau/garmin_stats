"""Dashboard overview read use case for Garmin analytics."""

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import DashboardOverviewResponse
from app.domains.garmin_analytics.domain.dashboard import compute_dashboard_overview


def get_dashboard_overview(
    repo: BiometricReadRepository,
) -> DashboardOverviewResponse:
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No data available")
    return compute_dashboard_overview(metrics)
