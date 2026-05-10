"""Architecture guard rails for global shared bucket imports."""

from tests._architecture import (
    REPO_ROOT,
    assert_imports_from_module_match_allowlist,
    assert_no_text_in_files,
)

ALLOWLISTED_APP_MODELS_IMPORTERS = set()

ALLOWLISTED_APP_STATS_IMPORTERS = set()

ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS = {
    "backend/app/core/profile/infra/sqlite_repository.py",
    "backend/app/domains/assistant/infra/sqlite_repository.py",
    "backend/app/domains/experiments/infra/sqlite_repository.py",
    "backend/app/domains/journal/infra/sqlite_repository.py",
    "backend/app/domains/programs/infra/sqlite_repository.py",
}

ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS = {
    "backend/app/domains/garmin_sync/sqlite_ingest.py",
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
