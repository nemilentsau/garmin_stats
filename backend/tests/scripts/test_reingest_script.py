"""Regression tests for utility scripts that run outside the FastAPI server."""

import runpy

from tests._architecture import REPO_ROOT


def test_reingest_script_imports_current_storage_bootstrap():
    runpy.run_path(str(REPO_ROOT / "scripts/reingest.py"), run_name="__not_main__")
