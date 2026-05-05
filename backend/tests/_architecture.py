"""Shared helpers for architecture boundary tests."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


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
