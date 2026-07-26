"""Regression tests for utility scripts that run outside the FastAPI server."""

import runpy

from tests._architecture import REPO_ROOT, read_repo_file


def test_reingest_script_imports_current_storage_bootstrap():
    runpy.run_path(str(REPO_ROOT / "scripts/reingest.py"), run_name="__not_main__")


def test_reingest_scripts_refresh_data_dependents_without_coach_reconciliation():
    wellness_source = read_repo_file("scripts/reingest.py")
    activities_source = read_repo_file("scripts/reingest_activities.py")

    assert "trigger_ingest" in wellness_source
    assert "notify_data_changed" in activities_source
    assert "reconcile_pending" not in wellness_source + activities_source
