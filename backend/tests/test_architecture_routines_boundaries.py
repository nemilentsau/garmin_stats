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


def test_routines_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/routines/application/catalog.py",
        "backend/app/domains/routines/application/schedule_window.py",
        "backend/app/domains/routines/application/today.py",
        "backend/app/domains/routines/application/activation.py",
    ]:
        assert "fastapi" not in _read(path)


def test_flat_routines_routers_are_compatibility_wrappers():
    source = _read("backend/app/routers/routines.py")
    assert "domains.routines.api.routines" in source
    assert "APIRouter(" not in source
