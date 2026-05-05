"""Architecture guard rails for app-level profile configuration."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_REPO_ROOT / path).read_text(encoding="utf-8")


def test_profile_api_lives_under_core_not_flat_router_or_domain():
    source = _read("backend/app/core/profile/api.py")

    assert "APIRouter" in source
    assert "app.core.profile.application" in source
    assert "app.services." not in source
    assert "app.routers" not in source


def test_profile_application_is_fastapi_free():
    assert "fastapi" not in _read("backend/app/core/profile/application.py")


def test_bootstrap_routing_mounts_core_profile_router_directly():
    source = _read("backend/app/bootstrap/routing.py")

    assert "app.core.profile.api" in source
    assert "from ..routers.profile import router as profile_router" not in source
    assert "include_router(profile_router)" in source


def test_migrated_profile_flat_files_are_removed():
    for path in [
        "backend/app/routers/profile.py",
        "backend/app/services/profile.py",
    ]:
        assert not (_REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_profile_flat_paths():
    forbidden = [
        "app.services.profile",
        "app.routers.profile",
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
