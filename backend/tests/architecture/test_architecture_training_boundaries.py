"""Architecture guard rails for the training domain slice."""

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    read_repo_file,
)


def test_training_route_module_does_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/training/routes.py",
    ])


def test_training_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/training/dependencies.py",
        "backend/app/domains/training/application/compile.py",
        "backend/app/domains/training/application/validation.py",
        "backend/app/domains/training/application/imports.py",
        "backend/app/domains/training/application/read_models.py",
    ])


def test_training_uses_flat_capability_layout():
    for path in [
        "backend/app/domains/training/api",
        "backend/app/domains/training/infra",
        "backend/app/domains/training/application/ports.py",
    ]:
        assert not (REPO_ROOT / path).exists()

    for path in [
        "backend/app/domains/training/routes.py",
        "backend/app/domains/training/adapters.py",
        "backend/app/domains/training/dependencies.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_training_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/training/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteTrainingRepository" in source


def test_training_routes_use_container_repository():
    source = read_repo_file("backend/app/domains/training/routes.py")
    assert "build_container" in source
    assert "training_repo" in source


def test_bootstrap_routing_mounts_domain_training_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.training.routes" in source
    assert "domains.training.api" not in source
    assert "include_router(training_router)" in source
