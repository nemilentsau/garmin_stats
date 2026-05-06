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


def test_programs_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/programs/api/programs.py",
    ])


def test_programs_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/programs/application/ports.py",
        "backend/app/domains/programs/application/programs.py",
    ])


def test_bootstrap_routing_mounts_domain_programs_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.programs.api.programs" in source
    assert "from ..routers.programs import router as programs_router" not in source
    assert "include_router(programs_router)" in source


def test_programs_domain_does_not_write_legacy_routine_or_experiment_children():
    assert_no_text_in_files(
        [
            "backend/app/domains/programs/application/ports.py",
            "backend/app/domains/programs/application/programs.py",
            "backend/app/domains/programs/infra/sqlite_repository.py",
        ],
        [
            "Routine",
            "Experiment",
            "replace_program_import",
            "_protocol_to_routine",
            "_spec_experiment_to_model",
        ],
    )


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
