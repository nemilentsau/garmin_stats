"""Architecture guard rails for the programs domain slice."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    assert_no_text_in_files,
    read_repo_file,
)


def test_programs_route_module_does_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/programs/routes.py",
    ])


def test_programs_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/programs/dependencies.py",
        "backend/app/domains/programs/application/programs.py",
    ])


def test_programs_uses_flat_capability_layout():
    for path in [
        "backend/app/domains/programs/api",
        "backend/app/domains/programs/infra",
        "backend/app/domains/programs/application/ports.py",
    ]:
        assert not (REPO_ROOT / path).exists()

    for path in [
        "backend/app/domains/programs/routes.py",
        "backend/app/domains/programs/adapters.py",
        "backend/app/domains/programs/dependencies.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_programs_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/programs/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteProgramRepository" in source
    assert "def save_program_import(" in source


def test_programs_routes_use_container_repository():
    source = read_repo_file("backend/app/domains/programs/routes.py")
    assert "build_container" in source
    assert "programs_repo" in source


def test_bootstrap_routing_mounts_domain_programs_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    legacy_api_import = "domains.programs." "api.programs"

    assert "domains.programs.routes" in source
    assert legacy_api_import not in source
    assert "from ..routers.programs import router as programs_router" not in source
    assert "include_router(programs_router)" in source


def test_programs_domain_does_not_write_legacy_routine_or_experiment_children():
    assert_no_text_in_files(
        [
            "backend/app/domains/programs/dependencies.py",
            "backend/app/domains/programs/application/programs.py",
            "backend/app/domains/programs/adapters.py",
        ],
        [
            "Routine",
            "Experiment",
            "replace_program_import",
            "_protocol_to_routine",
            "_spec_experiment_to_model",
        ],
    )


def test_shared_database_does_not_own_program_contracts_or_crud():
    source = read_repo_file("backend/app/infra/database.py")
    assert "domains.programs.contracts" not in source

    program_persistence_functions = [
        "def save_program(",
        "def load_program(",
        "def load_programs(",
        "def save_program_version(",
        "def load_program_versions(",
        "def delete_program(",
        "def save_program_import(",
    ]
    assert [name for name in program_persistence_functions if name in source] == []


def test_migrated_programs_service_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/services/programs.py").exists()


def test_migrated_programs_router_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/routers/programs.py").exists()


def test_backend_code_does_not_import_migrated_programs_shims():
    assert_no_repo_imports_of(
        [
            "app.services.programs",
            "app.routers.programs",
            "..services.programs",
            "..routers.programs",
        ],
        Path(__file__),
    )
