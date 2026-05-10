"""Architecture guard rails for the journal domain slice."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    assert_no_text_in_files,
    read_repo_file,
)


def test_journal_route_module_does_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/journal/routes.py",
    ])


def test_journal_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/journal/dependencies.py",
        "backend/app/domains/journal/application/checkins.py",
        "backend/app/domains/journal/application/notes.py",
    ])


def test_journal_uses_flat_capability_layout():
    for path in [
        "backend/app/domains/journal/api",
        "backend/app/domains/journal/infra",
        "backend/app/domains/journal/application/ports.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_journal_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/journal/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteJournalRepository" in source


def test_bootstrap_routing_mounts_domain_journal_routers_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.journal.routes" in source
    assert "domains.journal.api.checkins" not in source
    assert "domains.journal.api.notes" not in source
    assert "from ..routers.checkins import router as checkins_router" not in source
    assert "from ..routers.notes import router as notes_router" not in source
    assert "include_router(checkins_router)" in source
    assert "include_router(notes_router)" in source


def test_journal_routes_use_container_repository():
    source = read_repo_file("backend/app/domains/journal/routes.py")

    assert "build_container" in source
    assert "journal_repo" in source
    assert "checkins_router" in source
    assert "notes_router" in source


def test_shared_database_does_not_own_journal_contracts_or_crud():
    source = read_repo_file("backend/app/infra/database.py")
    assert "domains.journal.contracts" not in source

    journal_persistence_functions = [
        "def save_daily_checkin(",
        "def load_daily_checkins(",
        "def _fetch_all_daily_checkins(",
        "def save_note(",
        "def load_notes(",
    ]
    assert [name for name in journal_persistence_functions if name in source] == []


def test_journal_application_does_not_import_other_domains():
    assert_no_text_in_files(
        [
            "backend/app/domains/journal/dependencies.py",
            "backend/app/domains/journal/application/checkins.py",
            "backend/app/domains/journal/application/notes.py",
            "backend/app/domains/journal/adapters.py",
        ],
        [
            "app.domains.assistant",
            "app.domains.artifacts",
            "app.domains.experiments",
            "app.domains.garmin_analytics",
            "app.domains.garmin_sync",
            "app.domains.programs",
            "app.domains.routines",
        ],
    )


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
