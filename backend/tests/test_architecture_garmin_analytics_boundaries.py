"""Architecture guard rails for Garmin analytics domain ownership."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_REPO_ROOT / path).read_text(encoding="utf-8")


def test_garmin_analytics_api_modules_do_not_import_global_database_or_stats():
    for path in [
        "backend/app/domains/garmin_analytics/api/overview.py",
        "backend/app/domains/garmin_analytics/api/biometrics.py",
    ]:
        source = _read(path)
        assert "app.infra.database" not in source
        assert "app.stats" not in source
        assert "app.routers" not in source


def test_garmin_analytics_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/garmin_analytics/application/overview.py",
        "backend/app/domains/garmin_analytics/application/biometrics.py",
        "backend/app/domains/garmin_analytics/application/period_summary.py",
        "backend/app/domains/garmin_analytics/application/insights.py",
    ]:
        assert "fastapi" not in _read(path)


def test_bootstrap_routing_mounts_domain_garmin_analytics_routers_directly():
    source = _read("backend/app/bootstrap/routing.py")
    assert "domains.garmin_analytics.api.overview" in source
    assert "domains.garmin_analytics.api.biometrics" in source
    assert "from ..routers.dashboard import router as dashboard_router" not in source
    assert "from ..routers.wellness import router as wellness_router" not in source
    assert "from ..routers.sleep import router as sleep_router" not in source
    assert "from ..routers.hrv import router as hrv_router" not in source
    assert "from ..routers.skin_temp import router as skin_temp_router" not in source
    assert "from ..routers.daily_aggregates import router as daily_aggregates_router" not in source


def test_flat_garmin_analytics_routers_are_compatibility_wrappers():
    for path in [
        "backend/app/routers/dashboard.py",
        "backend/app/routers/wellness.py",
        "backend/app/routers/sleep.py",
        "backend/app/routers/hrv.py",
        "backend/app/routers/skin_temp.py",
        "backend/app/routers/daily_aggregates.py",
    ]:
        source = _read(path)
        assert "domains.garmin_analytics.api" in source
        assert "APIRouter(" not in source


def test_days_route_remains_outside_garmin_analytics_slice():
    source = _read("backend/app/bootstrap/routing.py")
    assert "from ..routers.days import router as days_router" in source
    assert "domains.garmin_analytics.api.days" not in source
