"""Architecture guard rails for app-level profile configuration."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    read_repo_file,
)


def test_profile_api_lives_under_core_not_flat_router_or_domain():
    source = read_repo_file("backend/app/core/profile/api.py")

    assert "APIRouter" in source
    assert "app.core.profile.application" in source
    assert_api_modules_are_boundary_only(["backend/app/core/profile/api.py"])


def test_profile_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/core/profile/application.py",
        "backend/app/core/profile/ports.py",
    ])


def test_profile_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/core/profile/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteProfileRepository" in source


def test_bootstrap_routing_mounts_core_profile_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "app.core.profile.api" in source
    assert "from ..routers.profile import router as profile_router" not in source
    assert "include_router(profile_router)" in source


def test_profile_routes_use_container_repository():
    source = read_repo_file("backend/app/core/profile/api.py")

    assert "build_container" in source
    assert "profile_repo" in source


def test_migrated_profile_flat_files_are_removed():
    for path in [
        "backend/app/core/profile/infra/__init__.py",
        "backend/app/core/profile/infra/sqlite_repository.py",
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
