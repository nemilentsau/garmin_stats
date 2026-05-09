"""Architecture guard rails for global shared bucket imports."""

from tests._architecture import (
    assert_imports_from_module_match_allowlist,
    assert_no_text_in_files,
)

ALLOWLISTED_APP_MODELS_IMPORTERS = {
    "backend/app/core/profile/api.py",
    "backend/app/core/profile/application.py",
    "backend/app/core/profile/infra/sqlite_repository.py",
    "backend/app/core/profile/ports.py",
    "backend/app/domains/artifacts/api/artifacts.py",
    "backend/app/domains/artifacts/api/bundles.py",
    "backend/app/domains/artifacts/application/artifacts.py",
    "backend/app/domains/artifacts/application/ports.py",
    "backend/app/domains/artifacts/infra/sqlite_repository.py",
    "backend/app/domains/assistant/api/threads.py",
    "backend/app/domains/assistant/application/chat.py",
    "backend/app/domains/assistant/application/entity_resolution.py",
    "backend/app/domains/assistant/application/ports.py",
    "backend/app/domains/assistant/application/retrieval.py",
    "backend/app/domains/assistant/application/threads.py",
    "backend/app/domains/assistant/infra/sqlite_repository.py",
    "backend/app/domains/experiments/api/experiments.py",
    "backend/app/domains/experiments/api/target_metrics.py",
    "backend/app/domains/experiments/application/analysis.py",
    "backend/app/domains/experiments/application/analysis_cache.py",
    "backend/app/domains/experiments/application/analysis_math.py",
    "backend/app/domains/experiments/application/exposure_sync.py",
    "backend/app/domains/experiments/application/exposures.py",
    "backend/app/domains/experiments/application/management.py",
    "backend/app/domains/experiments/application/ports.py",
    "backend/app/domains/experiments/application/preview.py",
    "backend/app/domains/experiments/application/target_metrics.py",
    "backend/app/domains/experiments/infra/sqlite_repository.py",
    "backend/app/domains/journal/api/checkins.py",
    "backend/app/domains/journal/api/notes.py",
    "backend/app/domains/journal/application/checkins.py",
    "backend/app/domains/journal/application/notes.py",
    "backend/app/domains/journal/application/ports.py",
    "backend/app/domains/journal/infra/sqlite_repository.py",
    "backend/app/domains/programs/api/programs.py",
    "backend/app/domains/programs/application/ports.py",
    "backend/app/domains/programs/application/programs.py",
    "backend/app/domains/programs/infra/sqlite_repository.py",
    "backend/app/domains/routines/application/activation.py",
}

ALLOWLISTED_APP_STATS_IMPORTERS = set()

ALLOWLISTED_APP_INFRA_DATABASE_IMPORTERS = {
    "backend/app/core/profile/infra/sqlite_repository.py",
    "backend/app/domains/artifacts/infra/sqlite_repository.py",
    "backend/app/domains/assistant/infra/sqlite_repository.py",
    "backend/app/domains/experiments/infra/sqlite_repository.py",
    "backend/app/domains/garmin_sync/adapters.py",
    "backend/app/domains/journal/infra/sqlite_repository.py",
    "backend/app/domains/programs/infra/sqlite_repository.py",
    "backend/app/domains/routines/infra/sqlite_repository.py",
}

ALLOWLISTED_APP_INFRA_CACHE_IMPORTERS = {
    "backend/app/domains/garmin_analytics/application/daily_aggregates.py",
    "backend/app/domains/garmin_analytics/application/metric_analysis.py",
    "backend/app/domains/garmin_analytics/adapters.py",
}


def test_app_models_importers_are_explicitly_allowlisted():
    assert_imports_from_module_match_allowlist(
        "app.models",
        ALLOWLISTED_APP_MODELS_IMPORTERS,
    )


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
