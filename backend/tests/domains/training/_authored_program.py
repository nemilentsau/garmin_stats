"""Read the latest authored program from its canonical import package."""

from __future__ import annotations

import json
from typing import Any
from zipfile import ZipFile

from tests._architecture import REPO_ROOT

AUTHORED_PROGRAM_DIR = (
    REPO_ROOT
    / "docs"
    / "training"
    / "programs"
    / "threshold-development-2026-07-13"
)
AUTHORED_PROGRAM_PACKAGE = AUTHORED_PROGRAM_DIR / "threshold-development-2026-07-13.zip"
AUTHORED_ARTIFACT_NAMES = frozenset(
    {
        "block1.json",
        "running_v3.json",
        "strength_v3.json",
        "support_v3.json",
        "registry.json",
        "exercise_library.json",
    }
)


def load_authored_artifact(name: str) -> dict[str, Any]:
    """Load one authored JSON object without extracting the canonical ZIP."""
    with ZipFile(AUTHORED_PROGRAM_PACKAGE) as package:
        parsed = json.loads(package.read(name).decode("utf-8"))
    assert isinstance(parsed, dict)
    return parsed
