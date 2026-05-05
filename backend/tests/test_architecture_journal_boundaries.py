"""Architecture guard rails for the journal domain slice."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_REPO_ROOT / path).read_text(encoding="utf-8")


def test_journal_api_modules_do_not_import_flat_database_or_services():
    for path in [
        "backend/app/domains/journal/api/checkins.py",
        "backend/app/domains/journal/api/notes.py",
    ]:
        source = _read(path)
        assert "app.infra.database" not in source
        assert "app.services." not in source
        assert "app.routers" not in source


def test_journal_application_modules_are_fastapi_free():
    for path in [
        "backend/app/domains/journal/application/checkins.py",
        "backend/app/domains/journal/application/notes.py",
    ]:
        assert "fastapi" not in _read(path)


def test_journal_application_does_not_import_flat_services_or_routers():
    for path in [
        "backend/app/domains/journal/application/checkins.py",
        "backend/app/domains/journal/application/notes.py",
    ]:
        source = _read(path)
        assert "app.services" not in source
        assert "app.routers" not in source


def test_bootstrap_routing_mounts_domain_journal_routers_directly():
    source = _read("backend/app/bootstrap/routing.py")

    assert "domains.journal.api.checkins" in source
    assert "domains.journal.api.notes" in source
    assert "from ..routers.checkins import router as checkins_router" not in source
    assert "from ..routers.notes import router as notes_router" not in source
    assert "include_router(checkins_router)" in source
    assert "include_router(notes_router)" in source


def test_migrated_journal_service_shims_are_removed():
    for path in [
        "backend/app/services/checkins.py",
        "backend/app/services/notes.py",
    ]:
        assert not (_REPO_ROOT / path).exists()


def test_migrated_journal_router_shims_are_removed():
    for path in [
        "backend/app/routers/checkins.py",
        "backend/app/routers/notes.py",
    ]:
        assert not (_REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_journal_shims():
    forbidden = [
        "app.services.checkins",
        "app.services.notes",
        "app.routers.checkins",
        "app.routers.notes",
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
