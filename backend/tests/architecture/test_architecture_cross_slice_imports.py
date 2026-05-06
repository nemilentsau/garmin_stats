"""Architecture guard rails for cross-slice imports."""

from tests._architecture import assert_cross_slice_imports_are_allowlisted


ALLOWLISTED_CROSS_SLICE_IMPORTS = {
    "backend/app/domains/artifacts/application/artifacts.py": {
        "app.domains.routines.application.activation",
        "app.domains.routines.application.ports",
    },
    "backend/app/domains/experiments/application/management.py": {
        "app.domains.routines.application.ports",
    },
    "backend/app/domains/experiments/application/preview.py": {
        "app.domains.routines.application.ports",
    },
    "backend/app/domains/experiments/application/exposure_sync.py": {
        "app.domains.routines.application.ports",
        "app.domains.routines.application.schedule_window",
    },
    "backend/app/domains/assistant/infra/sqlite_repository.py": {
        "app.domains.experiments.application.analysis_cache",
        "app.domains.experiments.application.ports",
    },
}


def test_cross_slice_imports_are_explicitly_allowlisted():
    assert_cross_slice_imports_are_allowlisted(ALLOWLISTED_CROSS_SLICE_IMPORTS)
