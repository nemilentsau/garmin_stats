"""Shared helpers for architecture boundary tests."""

from collections.abc import Iterable, Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


_STRICT_APPLICATION_FORBIDDEN: tuple[str, ...] = (
    "fastapi",
    "app.infra.database",
    "build_container",
    "app.services",
    "app.routers",
)


def assert_no_text_in_files(paths: Iterable[str], forbidden: Iterable[str]) -> None:
    forbidden_values = tuple(forbidden)
    sources = {path: read_repo_file(path) for path in paths}
    _assert_no_text_in_sources(sources, forbidden_values)


def _assert_no_text_in_sources(
    sources: Mapping[str, str], forbidden: Iterable[str],
) -> None:
    forbidden_values = tuple(forbidden)
    offenders = {
        path: matches
        for path, source in sources.items()
        if (matches := [value for value in forbidden_values if value in source])
    }
    assert offenders == {}


def assert_api_modules_are_boundary_only(paths: Iterable[str]) -> None:
    assert_no_text_in_files(
        paths,
        [
            "app.infra.database",
            "app.services.",
            "app.routers",
        ],
    )


def assert_application_modules_are_strict(paths: Iterable[str]) -> None:
    assert_no_text_in_files(paths, _STRICT_APPLICATION_FORBIDDEN)


def assert_transitional_application_modules(
    paths: Iterable[str],
    *,
    allowed_violations: Iterable[str],
    reason: str,
) -> None:
    """Document application-layer boundary exceptions for unfinished migrations.

    `reason` is required so the violation must be justified at the call site;
    it is not introspected at runtime.
    """
    del reason
    allowed = tuple(allowed_violations)
    sources = {path: read_repo_file(path) for path in paths}
    forbidden = [v for v in _STRICT_APPLICATION_FORBIDDEN if v not in allowed]
    _assert_no_text_in_sources(sources, forbidden)

    missing_allowed = [
        value for value in allowed if not any(value in source for source in sources.values())
    ]
    assert missing_allowed == []


def assert_no_repo_imports_of(forbidden: list[str], caller_file: Path) -> None:
    """Fail if any backend Python file references a forbidden import path.

    `caller_file` is excluded so the test file's own `forbidden` literals
    don't trigger the assertion.
    """
    caller = caller_file.resolve()
    roots = [REPO_ROOT / "backend" / "app", REPO_ROOT / "backend" / "tests"]

    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == caller:
                continue
            source = path.read_text(encoding="utf-8")
            if any(import_path in source for import_path in forbidden):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
