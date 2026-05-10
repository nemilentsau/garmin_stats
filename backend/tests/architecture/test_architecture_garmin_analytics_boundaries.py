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
        "backend/app/domains/garmin_analytics/routes.py",
    ]
    assert_api_modules_are_boundary_only(paths)
    assert_no_text_in_files(paths, ["app.stats"])


def test_garmin_analytics_application_does_not_import_flat_services_or_database():
    assert_application_modules_are_strict([
        "backend/app/domains/garmin_analytics/application/dashboard.py",
        "backend/app/domains/garmin_analytics/application/raw_biometrics.py",
        "backend/app/domains/garmin_analytics/application/daily_aggregates.py",
        "backend/app/domains/garmin_analytics/application/metric_analysis.py",
        "backend/app/domains/garmin_analytics/application/metric_insights.py",
        "backend/app/domains/garmin_analytics/application/dependencies.py",
    ])


def test_garmin_analytics_application_files_are_named_by_use_case_concern():
    app_root = REPO_ROOT / "backend/app/domains/garmin_analytics/application"

    for filename in [
        "dashboard.py",
        "raw_biometrics.py",
        "daily_aggregates.py",
        "metric_analysis.py",
        "metric_insights.py",
        "dependencies.py",
    ]:
        assert (app_root / filename).exists()

    for filename in [
        "overview.py",
        "biometrics.py",
        "period_summary.py",
        "periods.py",
        "analysis.py",
        "insights.py",
    ]:
        assert not (app_root / filename).exists()


def test_daily_aggregates_owns_period_window_orchestration():
    source = read_repo_file(
        "backend/app/domains/garmin_analytics/application/daily_aggregates.py",
    )

    assert "load_windowed_period_summary" in source
    assert "_reconstruct_day_data" in source
    assert "app.domains.garmin_analytics.application.periods" not in source


def test_garmin_analytics_dashboard_calculations_live_in_domain():
    assert (REPO_ROOT / "backend/app/domains/garmin_analytics/domain/dashboard.py").exists()
    assert_no_text_in_files(
        ["backend/app/domains/garmin_analytics/application/dashboard.py"],
        [
            "import numpy",
            "np.",
            "def _compute_",
            "def _build_",
            "def _recovery_status",
        ],
    )


def test_garmin_analytics_metric_insights_do_not_proxy_metric_analysis():
    assert_no_text_in_files(
        ["backend/app/domains/garmin_analytics/application/metric_insights.py"],
        [
            "metric_analysis",
            "get_sleep_analysis",
            "get_hrv_analysis",
            "get_heart_rate_analysis",
            "get_stress_analysis",
            "get_body_battery_analysis",
            "get_hr_distribution",
        ],
    )


def test_garmin_analytics_does_not_own_canonical_daily_metric_composer():
    base = REPO_ROOT / "backend/app/domains/garmin_analytics/domain/aggregates"
    analytics_root = REPO_ROOT / "backend/app/domains/garmin_analytics"
    database_source = read_repo_file("backend/app/infra/database.py")

    assert not (analytics_root / "utils.py").exists()
    assert not (analytics_root / "contracts/daily.py").exists()
    assert not (analytics_root / "contracts/readings.py").exists()
    assert not (base / "daily.py").exists()
    assert not (base / "daily_metrics").exists()
    assert not (
        REPO_ROOT
        / "backend/app/domains/garmin_analytics/domain/primitives/numeric.py"
    ).exists()
    assert "domains.garmin_analytics.utils" not in database_source
    assert "domains.garmin_analytics.domain.aggregates.daily" not in database_source


def test_heart_rate_resting_policy_has_single_metric_helper():
    daily_source = read_repo_file(
        "backend/app/domains/garmin_health/domain/daily_metrics/heart_rate.py",
    )
    period_source = read_repo_file(
        "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/heart_rate.py",
    )

    assert "def latest_resting_hr" in daily_source
    assert "def _latest_resting_hr" not in daily_source
    assert "def _latest_resting_hr" not in period_source
    assert "latest_resting_hr(day.wellness)" in period_source


def test_hrv_status_normalization_lives_with_hrv_daily_metric():
    hrv_source = read_repo_file(
        "backend/app/domains/garmin_health/domain/daily_metrics/hrv.py",
    )
    heart_rate_source = read_repo_file(
        "backend/app/domains/garmin_health/domain/daily_metrics/heart_rate.py",
    )

    assert "def normalize_hrv_status" in hrv_source
    assert "normalize_hrv_status" not in heart_rate_source


def test_hrv_status_consumers_use_normalized_labels_not_substring_matching():
    assert_no_text_in_files(
        [
            "backend/app/domains/garmin_analytics/domain/dashboard.py",
            "backend/app/domains/garmin_analytics/domain/insights/heart_rate.py",
            "backend/app/domains/garmin_analytics/domain/insights/hrv.py",
            "backend/app/domains/garmin_analytics/domain/aggregates/period_metrics/hrv.py",
        ],
        [
            ".status.lower()",
            "status.lower()",
            '"balanced" in',
            '"unbalanced" in',
            '"low" in',
        ],
    )


def test_period_aggregate_composer_delegates_to_metric_modules():
    base = REPO_ROOT / "backend/app/domains/garmin_analytics/domain/aggregates"
    for filename in [
        "__init__.py",
        "heart_rate.py",
        "stress.py",
        "body_battery.py",
        "spo2.py",
        "respiration.py",
        "hrv.py",
        "sleep.py",
        "skin_temp.py",
    ]:
        assert (base / "period_metrics" / filename).exists()

    source = read_repo_file(
        "backend/app/domains/garmin_analytics/domain/aggregates/period.py",
    )
    assert "all_hr =" not in source
    assert "all_stress =" not in source
    assert "spo2_day_mins" not in source
    assert "skin_devs" not in source
    assert "sleep_scores" not in source
    assert "bb_mins" not in source
    assert "PeriodHeartRateStats(" not in source
    assert "PeriodMetricStats(" not in source
    assert "PeriodBodyBatteryStats(" not in source


def test_garmin_analytics_uses_contract_dependency_adapter_route_layout():
    base = REPO_ROOT / "backend/app/domains/garmin_analytics"

    assert (base / "contracts").is_dir()
    assert (base / "application/dependencies.py").exists()
    assert (base / "adapters.py").exists()
    assert (base / "routes.py").exists()
    assert not (base / "application/ports.py").exists()
    assert not list((base / "api").glob("*.py"))
    assert not list((base / "infra").glob("*.py"))


def test_garmin_analytics_contracts_are_split_by_concern_with_stable_imports():
    import app.domains.garmin_analytics.contracts as contracts

    base = REPO_ROOT / "backend/app/domains/garmin_analytics"
    contracts_root = base / "contracts"

    assert not (base / "contracts.py").exists()
    for filename in [
        "__init__.py",
        "raw.py",
        "period.py",
        "insights.py",
        "analysis.py",
        "dashboard.py",
    ]:
        assert (contracts_root / filename).exists()

    assert contracts.DailyAggregatesResponse.__name__ == "DailyAggregatesResponse"
    assert contracts.DashboardOverviewResponse.__name__ == "DashboardOverviewResponse"


def test_garmin_analytics_imports_owned_contracts_directly():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/garmin_analytics").rglob(
            "*.py",
        )
        if "__pycache__" not in path.parts
    ]
    assert_no_text_in_files(
        paths,
        ["from app.models import", "import app.models"],
    )


def test_garmin_biometric_sqlite_reads_have_single_adapter_implementation():
    database_source = read_repo_file("backend/app/infra/database.py")
    adapter_source = read_repo_file("backend/app/domains/garmin_analytics/adapters.py")
    assistant_repo_source = read_repo_file("backend/app/domains/assistant/adapters.py")
    experiment_repo_source = read_repo_file(
        "backend/app/domains/experiments/adapters.py",
    )

    assert "domains.garmin_analytics.adapters" not in database_source
    assert "def _load_day_table" not in database_source
    assert "def _fetch_daily_metrics" not in database_source
    for wrapper_name in [
        "load_daily_metrics",
        "load_wellness",
        "load_sleep",
        "load_hrv",
        "load_skin_temp",
    ]:
        assert f"def {wrapper_name}" not in database_source

    assert "def load_daily_metrics" in adapter_source
    assert "class SqliteBiometricRepository" in adapter_source
    assert "from app.domains.garmin_analytics.adapters import load_daily_metrics" in (
        assistant_repo_source
    )
    assert "from app.domains.garmin_analytics.adapters import load_daily_metrics" in (
        experiment_repo_source
    )


def test_global_models_do_not_reexport_garmin_analytics_contracts():
    assert not (REPO_ROOT / "backend/app/models.py").exists()


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
    assert "domains.garmin_analytics.routes" in source
    assert "domains.garmin_analytics.api." not in source
    assert "from ..routers.dashboard import router as dashboard_router" not in source
    assert "from ..routers.wellness import router as wellness_router" not in source
    assert "from ..routers.sleep import router as sleep_router" not in source
    assert "from ..routers.hrv import router as hrv_router" not in source
    assert "from ..routers.skin_temp import router as skin_temp_router" not in source
    assert "from ..routers.daily_aggregates import router as daily_aggregates_router" not in source
    assert "from ..routers.heart_rate import router as heart_rate_router" not in source
    assert "from ..routers.stress import router as stress_router" not in source
    assert "from ..routers.body_battery import router as body_battery_router" not in source


def test_broad_wellness_raw_endpoint_has_been_removed():
    routes = read_repo_file("backend/app/domains/garmin_analytics/routes.py")
    contracts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(
            (
                REPO_ROOT / "backend/app/domains/garmin_analytics/contracts"
            ).glob("*.py"),
        )
    )
    raw_biometrics = read_repo_file(
        "backend/app/domains/garmin_analytics/application/raw_biometrics.py",
    )
    responses = read_repo_file(
        "backend/app/domains/garmin_analytics/domain/aggregates/biometric_responses.py",
    )
    routing = read_repo_file("backend/app/bootstrap/routing.py")

    assert 'prefix="/api/wellness"' not in routes
    assert "wellness_router" not in routes
    assert "wellness_router" not in routing
    assert "def get_wellness" not in routes
    assert "def get_wellness" not in raw_biometrics
    assert "class WellnessResponse" not in contracts
    assert "def flatten_wellness" not in responses


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


def test_legacy_days_route_has_been_removed():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "days_router" not in source
    assert not (REPO_ROOT / "backend/app/routers/days.py").exists()
    assert "domains.garmin_analytics.api.days" not in source
