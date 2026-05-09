"""Architecture guard rails for cross-slice imports."""

from tests._architecture import assert_cross_slice_imports_are_allowlisted

ALLOWLISTED_CROSS_SLICE_IMPORTS = {
    "backend/app/domains/artifacts/application/artifacts.py": {
        "app.domains.routines.application.activation",
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/artifacts/application/ports.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/artifacts/infra/sqlite_repository.py": {
        "app.domains.routines.adapters",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/artifacts/api/cards.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/artifacts/contracts.py": {
        "app.domains.routines.contracts",
    },
    "backend/app/domains/experiments/application/management.py": {
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/experiments/application/analysis.py": {
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/application/analysis_math.py": {
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/application/ports.py": {
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
    },
    "backend/app/domains/experiments/application/preview.py": {
        "app.domains.garmin_analytics.contracts",
        "app.domains.routines.dependencies",
    },
    "backend/app/domains/experiments/application/exposure_sync.py": {
        "app.domains.routines.contracts",
        "app.domains.routines.dependencies",
        "app.domains.routines.application.schedule_window",
    },
    "backend/app/domains/experiments/infra/sqlite_repository.py": {
        "app.domains.garmin_analytics.adapters",
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
    },
    "backend/app/domains/assistant/application/ports.py": {
        "app.core.profile.contracts",
        "app.domains.experiments.contracts",
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/assistant/application/entity_resolution.py": {
        "app.domains.experiments.contracts",
    },
    "backend/app/domains/assistant/application/retrieval.py": {
        "app.core.profile.contracts",
        "app.domains.experiments.contracts",
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/assistant/infra/sqlite_repository.py": {
        "app.core.profile.contracts",
        "app.domains.experiments.application.analysis_cache",
        "app.domains.experiments.application.ports",
        "app.domains.experiments.contracts",
        "app.domains.garmin_analytics.adapters",
        "app.domains.garmin_analytics.contracts",
        "app.domains.journal.contracts",
        "app.domains.routines.adapters",
        "app.domains.routines.contracts",
    },
    "backend/app/domains/garmin_sync/adapters.py": {
        "app.core.config",
    },
}


def test_cross_slice_imports_are_explicitly_allowlisted():
    assert_cross_slice_imports_are_allowlisted(ALLOWLISTED_CROSS_SLICE_IMPORTS)
