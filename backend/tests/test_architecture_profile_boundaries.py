"""Architecture guard rails for app-level profile configuration."""

from pathlib import Path

from tests._architecture import REPO_ROOT, assert_no_repo_imports_of, read_repo_file


def test_profile_api_lives_under_core_not_flat_router_or_domain():
    source = read_repo_file("backend/app/core/profile/api.py")

    assert "APIRouter" in source
    assert "app.core.profile.application" in source
    assert "app.services." not in source
    assert "app.routers" not in source


def test_profile_application_is_fastapi_free():
    assert "fastapi" not in read_repo_file("backend/app/core/profile/application.py")


def test_bootstrap_routing_mounts_core_profile_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "app.core.profile.api" in source
    assert "from ..routers.profile import router as profile_router" not in source
    assert "include_router(profile_router)" in source


def test_migrated_profile_flat_files_are_removed():
    for path in [
        "backend/app/routers/profile.py",
        "backend/app/services/profile.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_profile_flat_paths():
    assert_no_repo_imports_of(
        [
            "app.services.profile",
            "app.routers.profile",
        ],
        Path(__file__),
    )
