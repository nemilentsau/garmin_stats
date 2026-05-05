"""Architecture guard rails for the journal domain slice."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    read_repo_file,
)


def test_journal_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/journal/api/checkins.py",
        "backend/app/domains/journal/api/notes.py",
    ])


def test_journal_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/journal/application/checkins.py",
        "backend/app/domains/journal/application/notes.py",
        "backend/app/domains/journal/application/ports.py",
    ])


def test_journal_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/journal/infra/sqlite_repository.py")

    assert "app.infra.database" in source
    assert "class SqliteJournalRepository" in source


def test_bootstrap_routing_mounts_domain_journal_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.journal.api.checkins" in source
    assert "domains.journal.api.notes" in source
    assert "from ..routers.checkins import router as checkins_router" not in source
    assert "from ..routers.notes import router as notes_router" not in source
    assert "include_router(checkins_router)" in source
    assert "include_router(notes_router)" in source


def test_journal_routes_use_container_repository():
    for path in [
        "backend/app/domains/journal/api/checkins.py",
        "backend/app/domains/journal/api/notes.py",
    ]:
        source = read_repo_file(path)
        assert "build_container" in source
        assert "journal_repo" in source


def test_migrated_journal_service_shims_are_removed():
    for path in [
        "backend/app/services/checkins.py",
        "backend/app/services/notes.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_migrated_journal_router_shims_are_removed():
    for path in [
        "backend/app/routers/checkins.py",
        "backend/app/routers/notes.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_journal_shims():
    assert_no_repo_imports_of(
        [
            "app.services.checkins",
            "app.services.notes",
            "app.routers.checkins",
            "app.routers.notes",
        ],
        Path(__file__),
    )
