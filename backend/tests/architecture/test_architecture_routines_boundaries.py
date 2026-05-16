"""Architecture guard rails for the routines domain slice."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    assert_no_text_in_files,
    read_repo_file,
)


def test_today_card_extends_schedule_occurrence_contract():
    from app.domains.routines.contracts import ScheduleOccurrence, TodayCard

    assert issubclass(TodayCard, ScheduleOccurrence)


def test_routines_api_modules_do_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/routines/routes.py",
    ])


def test_routines_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/routines/application/catalog.py",
        "backend/app/domains/routines/application/schedule_window.py",
        "backend/app/domains/routines/application/today.py",
        "backend/app/domains/routines/application/activation.py",
        "backend/app/domains/routines/dependencies.py",
    ])


def test_bootstrap_routing_mounts_domain_routines_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")

    assert "domains.routines.routes" in source
    assert "from ..routers.routines import router" not in source
    assert "from ..routers.today import router" not in source
    assert "include_router(routines_router)" in source
    assert "include_router(today_router)" in source


def test_routines_uses_flat_capability_layout():
    for path in [
        "backend/app/domains/routines/api",
        "backend/app/domains/routines/domain",
        "backend/app/domains/routines/infra",
        "backend/app/domains/routines/application/ports.py",
    ]:
        assert not (REPO_ROOT / path).exists()

    for path in [
        "backend/app/domains/routines/routes.py",
        "backend/app/domains/routines/adapters.py",
        "backend/app/domains/routines/dependencies.py",
        "backend/app/domains/routines/schedule.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_routines_application_does_not_import_artifacts():
    paths = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "backend/app/domains/routines").rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    assert_no_text_in_files(paths, ["app.domains.artifacts"])


def test_routine_adapter_does_not_expose_test_only_override_helpers():
    source = read_repo_file("backend/app/domains/routines/adapters.py")

    assert "def save_card_override(" not in source
    assert "def load_card_overrides(" not in source
    assert "def load_card_overrides_range(" in source


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
