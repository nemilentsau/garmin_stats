"""Architecture guard rails for the artifacts domain slice."""

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    read_repo_file,
)


def test_artifacts_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/artifacts/routes.py",
    ])


def test_artifacts_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/artifacts/application/activation.py",
        "backend/app/domains/artifacts/application/bundle_ids.py",
        "backend/app/domains/artifacts/application/bundles.py",
        "backend/app/domains/artifacts/application/cards.py",
        "backend/app/domains/artifacts/application/staging.py",
        "backend/app/domains/artifacts/application/validation.py",
    ])


def test_bootstrap_routing_mounts_domain_artifact_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.artifacts.routes" in source
    assert "domains.artifacts.api." not in source
    assert "from ..routers.assistant_artifacts import router" not in source
    assert "from ..routers.assistant_artifact_bundles import router" not in source
    assert "from ..routers.cards import router" not in source
    assert "include_router(assistant_artifacts_router)" in source
    assert "include_router(assistant_artifact_bundles_router)" in source
    assert "include_router(cards_router)" in source


def test_migrated_artifact_service_shim_is_removed():
    assert not (REPO_ROOT / "backend/app/services/training_specs.py").exists()


def test_migrated_artifact_router_shims_are_removed():
    for path in [
        "backend/app/domains/artifacts/application/artifacts.py",
        "backend/app/domains/artifacts/application/ports.py",
        "backend/app/domains/artifacts/api/artifacts.py",
        "backend/app/domains/artifacts/api/bundles.py",
        "backend/app/domains/artifacts/api/cards.py",
        "backend/app/domains/artifacts/infra/sqlite_repository.py",
        "backend/app/routers/assistant_artifacts.py",
        "backend/app/routers/assistant_artifact_bundles.py",
        "backend/app/routers/cards.py",
    ]:
        assert not (REPO_ROOT / path).exists()
