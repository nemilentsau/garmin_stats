"""Architecture guard rails for Garmin sync domain ownership."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    read_repo_file,
)


def test_garmin_sync_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/garmin_sync/routes.py",
    ])


def test_garmin_sync_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/garmin_sync/use_cases.py",
        "backend/app/domains/garmin_sync/ports.py",
    ])


def test_garmin_sync_infra_adapters_are_database_and_watcher_boundary():
    source = read_repo_file("backend/app/domains/garmin_sync/adapters.py")

    assert "app.infra.database" in source
    assert "app.infra.watcher" in source
    assert "class DatabaseIngestGateway" in source
    assert "class WatcherController" in source


def test_garmin_sync_routes_use_container_dependencies():
    source = read_repo_file("backend/app/domains/garmin_sync/routes.py")

    assert "build_container" in source
    assert "garmin_sync" in source


def test_bootstrap_routing_mounts_domain_garmin_sync_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.garmin_sync.routes" in source
    assert "from ..routers.ingest import router as ingest_router" not in source
    assert "include_router(ingest_router)" in source


def test_garmin_sync_uses_small_capability_layout_without_ceremonial_layers():
    base = REPO_ROOT / "backend/app/domains/garmin_sync"

    assert not list((base / "api").glob("*.py"))
    assert not list((base / "application").glob("*.py"))
    assert not list((base / "infra").glob("*.py"))


def test_migrated_garmin_sync_service_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/services/garmin_sync.py").exists()


def test_migrated_ingest_router_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/routers/ingest.py").exists()


def test_backend_code_does_not_import_migrated_garmin_sync_shims():
    assert_no_repo_imports_of(
        [
            "app.services.garmin_sync",
            "app.routers.ingest",
            "..services.garmin_sync",
            "..routers.ingest",
        ],
        Path(__file__),
    )
