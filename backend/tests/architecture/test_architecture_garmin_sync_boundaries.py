"""Architecture guard rails for Garmin sync domain ownership."""

import ast
from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    assert_no_text_in_files,
    read_repo_file,
)


def test_garmin_sync_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/garmin_sync/routes.py",
    ])


def test_garmin_sync_workflow_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/garmin_sync/workflows.py",
        "backend/app/domains/garmin_sync/dependencies.py",
    ])


def test_garmin_sync_owns_filesystem_watcher_and_sqlite_ingest_in_infra_package():
    base = REPO_ROOT / "backend/app/domains/garmin_sync"
    infra = base / "infra"

    assert (infra / "__init__.py").exists()
    assert (infra / "filesystem.py").exists()
    assert (infra / "sqlite_ingest.py").exists()
    assert (infra / "watcher.py").exists()
    assert (infra / "runtime.py").exists()
    assert (infra / "garmin_connect.py").exists()
    assert (infra / "factory.py").exists()

    assert not (base / "filesystem.py").exists()
    assert not (base / "sqlite_ingest.py").exists()
    assert not (base / "watcher.py").exists()
    assert not (base / "runtime.py").exists()
    assert not (base / "adapters.py").exists()

    source = read_repo_file("backend/app/domains/garmin_sync/infra/factory.py")
    ingest_source = read_repo_file("backend/app/domains/garmin_sync/infra/sqlite_ingest.py")

    assert "app.infra.database" not in source
    assert "app.infra.watcher" not in source
    assert "class DatabaseIngestGateway" in ingest_source
    assert "extract_archives=extract_existing_archives" in source
    assert "suspend_watcher=watcher.suspend" in source
    assert "resume_watcher=watcher.resume" in source


def test_garmin_sync_runtime_and_watcher_depend_on_injected_ports():
    runtime_source = read_repo_file("backend/app/domains/garmin_sync/infra/runtime.py")
    watcher_source = read_repo_file("backend/app/domains/garmin_sync/infra/watcher.py")

    assert "from app.domains.garmin_sync.infra.filesystem" not in runtime_source
    assert "from app.domains.garmin_sync.infra.sqlite_ingest" not in runtime_source
    assert "GarminSyncDependencies" in runtime_source

    assert "from app.domains.garmin_sync.infra.sqlite_ingest import ingest_all" not in (
        watcher_source
    )
    assert "class DataDirectoryWatcher" in watcher_source
    assert "global _last_fingerprint" not in watcher_source
    assert "global _suspended" not in watcher_source

    tree = ast.parse(watcher_source)
    module_assigned_names = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "_last_fingerprint" not in module_assigned_names
    assert "_suspended" not in module_assigned_names


def test_global_infra_does_not_own_garmin_watcher_or_source_fingerprint():
    assert not (REPO_ROOT / "backend/app/infra/watcher.py").exists()
    assert not (REPO_ROOT / "backend/app/infra/database.py").exists()


def test_global_database_does_not_import_garmin_sync_contracts():
    assert not (REPO_ROOT / "backend/app/infra/database.py").exists()


def test_garmin_sync_infra_factory_does_not_wrap_single_function_dependencies():
    source = read_repo_file("backend/app/domains/garmin_sync/infra/factory.py")

    assert "class ArchiveExtractor" not in source
    assert "class WatcherController" not in source
    assert "class SystemClock" not in source
    assert "class SystemSleeper" not in source


def test_garmin_sync_imports_owned_contracts_directly():
    assert_no_text_in_files(
        [
            "backend/app/domains/garmin_sync/routes.py",
            "backend/app/domains/garmin_sync/workflows.py",
            "backend/app/domains/garmin_sync/dependencies.py",
            "backend/app/domains/garmin_sync/infra/factory.py",
            "backend/app/domains/garmin_sync/infra/filesystem.py",
            "backend/app/domains/garmin_sync/infra/garmin_connect.py",
            "backend/app/domains/garmin_sync/infra/runtime.py",
            "backend/app/domains/garmin_sync/infra/sqlite_ingest.py",
            "backend/app/domains/garmin_sync/infra/watcher.py",
        ],
        ["from app.models import", "import app.models"],
    )


def test_garmin_sync_contracts_are_not_exposed_from_app_models():
    assert not (REPO_ROOT / "backend/app/models.py").exists()


def test_runtime_path_config_lives_in_shared_app_config_not_garmin_sync():
    assert not (REPO_ROOT / "backend/app/domains/garmin_sync/config.py").exists()

    source = read_repo_file("backend/app/core/config.py")
    assert "GARMIN_DB_PATH" in source
    assert "GARMIN_DATA_DIR" in source
    assert "GARMINTOKENS" in source

    garmin_sync_files = [
        "backend/app/domains/garmin_sync/workflows.py",
        "backend/app/domains/garmin_sync/dependencies.py",
        "backend/app/domains/garmin_sync/infra/factory.py",
        "backend/app/domains/garmin_sync/infra/filesystem.py",
        "backend/app/domains/garmin_sync/infra/garmin_connect.py",
        "backend/app/domains/garmin_sync/infra/runtime.py",
        "backend/app/domains/garmin_sync/infra/sqlite_ingest.py",
        "backend/app/domains/garmin_sync/infra/watcher.py",
    ]
    assert_no_text_in_files(garmin_sync_files, ["GARMIN_SYNC_"])


def test_garmin_connect_protocol_details_live_in_adapter_not_workflow():
    assert_no_text_in_files(
        [
            "backend/app/domains/garmin_sync/workflows.py",
            "backend/app/domains/garmin_sync/dependencies.py",
        ],
        [
            "/download-service/files",
            "MINIMUM_ARCHIVE_BYTES",
            "REQUEST_SPACING_SECONDS",
        ],
    )

    source = read_repo_file("backend/app/domains/garmin_sync/infra/garmin_connect.py")
    assert "/download-service/files/wellness" in source
    assert "_MINIMUM_ARCHIVE_BYTES" in source
    assert "_REQUEST_SPACING_SECONDS" in source


def test_garmin_sync_routes_use_container_dependencies():
    source = read_repo_file("backend/app/domains/garmin_sync/routes.py")

    assert "build_container" in source
    assert "garmin_sync" in source


def test_bootstrap_routing_mounts_domain_garmin_sync_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.garmin_sync.routes" in source
    assert "from ..routers.ingest import router as ingest_router" not in source
    assert "include_router(ingest_router)" in source


def test_lifespan_delegates_process_runtime_wiring():
    assert (REPO_ROOT / "backend/app/bootstrap/process_runtime.py").exists()

    lifespan_source = read_repo_file("backend/app/bootstrap/lifespan.py")
    runtime_source = read_repo_file("backend/app/bootstrap/process_runtime.py")

    assert "ProcessRuntime" in lifespan_source
    assert "refresh_active_experiments" not in lifespan_source
    assert "watch_data_directory" not in lifespan_source
    assert "run_startup_ingest_if_needed" not in lifespan_source

    assert "refresh_active_experiments" in runtime_source
    assert "run_startup_ingest_if_needed" in runtime_source


def test_garmin_sync_uses_small_capability_layout_with_only_owned_infra_layer():
    base = REPO_ROOT / "backend/app/domains/garmin_sync"

    assert not list((base / "api").glob("*.py"))
    assert not list((base / "application").glob("*.py"))
    assert sorted(path.name for path in (base / "infra").glob("*.py")) == [
        "__init__.py",
        "factory.py",
        "filesystem.py",
        "garmin_connect.py",
        "runtime.py",
        "sqlite_ingest.py",
        "watcher.py",
    ]


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
