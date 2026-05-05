"""Architecture guard rails for the routines domain slice."""

from pathlib import Path

from tests._architecture import REPO_ROOT, assert_no_repo_imports_of, read_repo_file


def test_routines_api_modules_do_not_import_flat_database_or_services():
    for path in [
        "backend/app/domains/routines/api/routines.py",
        "backend/app/domains/routines/api/today.py",
    ]:
        source = read_repo_file(path)
        assert "app.infra.database" not in source
        assert "app.services." not in source
        assert "app.routers" not in source


def test_routines_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/routines/application/catalog.py",
        "backend/app/domains/routines/application/schedule_window.py",
        "backend/app/domains/routines/application/today.py",
        "backend/app/domains/routines/application/activation.py",
    ]:
        assert "fastapi" not in read_repo_file(path)


def test_bootstrap_routing_mounts_domain_routines_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.routines.api.routines" in source
    assert "domains.routines.api.today" in source
    assert "from ..routers.routines import router" not in source
    assert "from ..routers.today import router" not in source
    assert "include_router(routines_router)" in source
    assert "include_router(today_router)" in source


def test_migrated_routine_service_shims_are_removed():
    for path in [
        "backend/app/services/routines.py",
        "backend/app/services/schedule_projection.py",
        "backend/app/services/today.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_migrated_routine_router_shims_are_removed():
    for path in [
        "backend/app/routers/routines.py",
        "backend/app/routers/today.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_routine_shims():
    assert_no_repo_imports_of(
        [
            "app.services.routines",
            "app.services.schedule_projection",
            "app.services.today",
            "app.routers.routines",
            "app.routers.today",
        ],
        Path(__file__),
    )
