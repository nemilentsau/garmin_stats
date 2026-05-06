"""Architecture guard rails for Garmin analytics domain ownership."""

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_text_in_files,
    read_repo_file,
)


def test_garmin_analytics_api_modules_do_not_import_global_database_or_stats():
    paths = [
        "backend/app/domains/garmin_analytics/api/overview.py",
        "backend/app/domains/garmin_analytics/api/biometrics.py",
        "backend/app/domains/garmin_analytics/api/insights.py",
    ]
    assert_api_modules_are_boundary_only(paths)
    assert_no_text_in_files(paths, ["app.stats"])


def test_garmin_analytics_application_does_not_import_flat_services_or_database():
    assert_application_modules_are_strict([
        "backend/app/domains/garmin_analytics/application/overview.py",
        "backend/app/domains/garmin_analytics/application/biometrics.py",
        "backend/app/domains/garmin_analytics/application/period_summary.py",
        "backend/app/domains/garmin_analytics/application/analysis.py",
        "backend/app/domains/garmin_analytics/application/insights.py",
    ])


def test_garmin_analytics_domain_modules_do_not_import_application_or_infra():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/garmin_analytics/domain").rglob(
            "*.py",
        )
    ]
    assert_no_text_in_files(
        paths,
        [
            "app.domains.garmin_analytics.application",
            "app.domains.garmin_analytics.infra",
            "app.infra",
            "fastapi",
        ],
    )


def test_garmin_analytics_analysis_modules_do_not_import_insights():
    analysis_root = REPO_ROOT / "backend/app/domains/garmin_analytics/domain/analysis"
    if not analysis_root.exists():
        return

    paths = [str(path.relative_to(REPO_ROOT)) for path in analysis_root.rglob("*.py")]
    assert_no_text_in_files(paths, ["app.domains.garmin_analytics.domain.insights"])


def test_migrated_garmin_analytics_service_shims_are_removed():
    for path in [
        "backend/app/services/dashboard.py",
        "backend/app/services/heart_rate.py",
        "backend/app/services/heart_rate_analysis.py",
        "backend/app/services/hrv.py",
        "backend/app/services/hrv_analysis.py",
        "backend/app/services/sleep_analysis.py",
        "backend/app/services/stress_analysis.py",
        "backend/app/services/body_battery_analysis.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_bootstrap_routing_mounts_domain_garmin_analytics_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.garmin_analytics.api.overview" in source
    assert "domains.garmin_analytics.api.biometrics" in source
    assert "domains.garmin_analytics.api.insights" in source
    assert "from ..routers.dashboard import router as dashboard_router" not in source
    assert "from ..routers.wellness import router as wellness_router" not in source
    assert "from ..routers.sleep import router as sleep_router" not in source
    assert "from ..routers.hrv import router as hrv_router" not in source
    assert "from ..routers.skin_temp import router as skin_temp_router" not in source
    assert "from ..routers.daily_aggregates import router as daily_aggregates_router" not in source
    assert "from ..routers.heart_rate import router as heart_rate_router" not in source
    assert "from ..routers.stress import router as stress_router" not in source
    assert "from ..routers.body_battery import router as body_battery_router" not in source


def test_migrated_garmin_analytics_router_shims_are_removed():
    for path in [
        "backend/app/routers/dashboard.py",
        "backend/app/routers/wellness.py",
        "backend/app/routers/sleep.py",
        "backend/app/routers/hrv.py",
        "backend/app/routers/skin_temp.py",
        "backend/app/routers/daily_aggregates.py",
        "backend/app/routers/heart_rate.py",
        "backend/app/routers/stress.py",
        "backend/app/routers/body_battery.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_days_route_remains_outside_garmin_analytics_slice():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "from ..routers.days import router as days_router" in source
    assert "domains.garmin_analytics.api.days" not in source
