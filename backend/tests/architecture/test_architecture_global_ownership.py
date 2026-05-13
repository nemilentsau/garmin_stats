"""Architecture guard rails for global shared bucket imports."""

from tests._architecture import (
    REPO_ROOT,
    assert_imports_from_module_match_allowlist,
    assert_no_text_in_files,
    read_repo_file,
)

ALLOWLISTED_APP_MODELS_IMPORTERS = set()

ALLOWLISTED_APP_STATS_IMPORTERS = set()

ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS = {
    "backend/app/core/profile/infra/sqlite_repository.py",
    "backend/app/domains/experiments/adapters.py",
}

ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS = {
    "backend/app/domains/journal/adapters.py",
    "backend/app/domains/garmin_sync/infra/sqlite_ingest.py",
    "backend/app/domains/garmin_analytics/application/daily_aggregates.py",
    "backend/app/domains/garmin_analytics/application/metric_analysis.py",
    "backend/app/domains/garmin_analytics/adapters.py",
}


def test_app_models_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.models",
        ALLOWLISTED_APP_MODELS_IMPORTERS,
    )


def test_app_models_file_has_been_removed():
    assert not (REPO_ROOT / "backend/app/models.py").exists()


def test_app_stats_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.stats",
        ALLOWLISTED_APP_STATS_IMPORTERS,
    )


def test_app_infra_database_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.infra.database",
        ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS,
    )


def test_app_infra_cache_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.infra.cache",
        ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS,
        equivalent_imports={"app.infra"},
        required_import_name="cache",
    )


def test_infra_database_does_not_own_domain_table_schema_names():
    source = read_repo_file("backend/app/infra/database.py")
    domain_table_names = [
        "assistant_messages",
        "routine_assignments",
        "experiment_exposures",
        "program_versions",
        "assistant_artifacts",
        "daily_checkins",
        "card_logs",
    ]
    assert [name for name in domain_table_names if name in source] == []


def test_current_docs_do_not_reference_removed_app_stats_module():
    assert_no_text_in_files(
        [
            "README.md",
            "docs/ARCHITECTURE.md",
            "backend/app/infra/database.py",
        ],
        [
            "backend/app/stats.py",
            "`backend/app/stats.py`",
            "`stats.py`",
            "parser → stats",
            "parser -> `stats.py`",
            "parser → `stats.py`",
        ],
    )


def test_global_infra_does_not_own_route_specific_response_contracts():
    assert not (REPO_ROOT / "backend/app/infra/contracts.py").exists()
    assert not (REPO_ROOT / "backend/app/routers/days.py").exists()


def test_realtime_transport_lives_in_dedicated_app_capability():
    assert not list((REPO_ROOT / "backend/app/routers").glob("*.py"))
    assert not (REPO_ROOT / "backend/app/infra/events.py").exists()
    assert (REPO_ROOT / "backend/app/realtime/events.py").exists()
    assert (REPO_ROOT / "backend/app/realtime/routes.py").exists()

    routing_source = (REPO_ROOT / "backend/app/bootstrap/routing.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (REPO_ROOT / "backend/app/bootstrap/process_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "app.realtime.routes" in routing_source
    assert "app.realtime.events" in runtime_source
    assert "routers.events" not in routing_source
    assert "infra.events" not in runtime_source
