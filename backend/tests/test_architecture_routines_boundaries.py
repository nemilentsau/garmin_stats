"""Architecture guard rails for the routines domain slice."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_REPO_ROOT / path).read_text(encoding="utf-8")


def test_routines_api_modules_do_not_import_flat_database_or_services():
    for path in [
        "backend/app/domains/routines/api/routines.py",
        "backend/app/domains/routines/api/today.py",
    ]:
        source = _read(path)
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
        assert "fastapi" not in _read(path)


def test_bootstrap_routing_mounts_domain_routines_router_directly():
    source = _read("backend/app/bootstrap/routing.py")

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
        assert not (_REPO_ROOT / path).exists()


def test_migrated_routine_router_shims_are_removed():
    for path in [
        "backend/app/routers/routines.py",
        "backend/app/routers/today.py",
    ]:
        assert not (_REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_routine_shims():
    forbidden = [
        "app.services.routines",
        "app.services.schedule_projection",
        "app.services.today",
        "app.routers.routines",
        "app.routers.today",
    ]
    roots = [
        _REPO_ROOT / "backend" / "app",
        _REPO_ROOT / "backend" / "tests",
    ]

    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            source = path.read_text(encoding="utf-8")
            if any(import_path in source for import_path in forbidden):
                offenders.append(str(path.relative_to(_REPO_ROOT)))

    assert offenders == []
