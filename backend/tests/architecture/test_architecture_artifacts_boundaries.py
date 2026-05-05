"""Architecture guard rails for the artifacts domain slice."""

from tests._architecture import REPO_ROOT, read_repo_file


def test_artifacts_api_modules_do_not_import_flat_database_or_services():
    for path in [
        "backend/app/domains/artifacts/api/artifacts.py",
        "backend/app/domains/artifacts/api/bundles.py",
        "backend/app/domains/artifacts/api/cards.py",
    ]:
        source = read_repo_file(path)
        assert "app.infra.database" not in source
        assert "app.services." not in source
        assert "app.routers" not in source


def test_artifacts_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/artifacts/application/artifacts.py",
    ]:
        assert "fastapi" not in read_repo_file(path)


def test_artifacts_application_does_not_import_flat_services_or_routers():
    for path in [
        "backend/app/domains/artifacts/application/artifacts.py",
    ]:
        source = read_repo_file(path)
        assert "app.services" not in source
        assert "app.routers" not in source


def test_bootstrap_routing_mounts_domain_artifact_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.artifacts.api.artifacts" in source
    assert "domains.artifacts.api.bundles" in source
    assert "domains.artifacts.api.cards" in source
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
        "backend/app/routers/assistant_artifacts.py",
        "backend/app/routers/assistant_artifact_bundles.py",
        "backend/app/routers/cards.py",
    ]:
        assert not (REPO_ROOT / path).exists()
