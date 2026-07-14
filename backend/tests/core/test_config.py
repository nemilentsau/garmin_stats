"""Tests for shared application configuration."""

from pathlib import Path

import pytest

from app.core.config import get_app_config


def test_app_config_uses_project_defaults_without_env_overrides():
    config = get_app_config({})

    assert config.database_path.name == "garmin_stats.db"
    assert config.database_path.parent.name == "storage"
    assert config.data_dir.name == "garmin_health_stats"
    assert config.data_dir.parent.name == "data"
    assert config.garmin_token_dir == Path("~/.garminconnect").expanduser()


def test_app_config_reads_runtime_path_env_overrides(tmp_path: Path):
    config = get_app_config({
        "GARMIN_DB_PATH": str(tmp_path / "test.db"),
        "GARMIN_DATA_DIR": str(tmp_path / "garmin-data"),
        "GARMINTOKENS": str(tmp_path / "tokens"),
    })

    assert config.database_path == tmp_path / "test.db"
    assert config.data_dir == tmp_path / "garmin-data"
    assert config.garmin_token_dir == tmp_path / "tokens"


def test_activities_dir_defaults_under_project_data_tree():
    config = get_app_config(environ={})
    assert config.activities_dir.name == "garmin_activities"
    assert config.activities_dir.parent.name == "data"
    assert config.activities_dir.parent == config.data_dir.parent


def test_activities_dir_reads_env_override():
    config = get_app_config(environ={"GARMIN_ACTIVITY_DATA_DIR": "/tmp/custom-activities"})
    assert config.activities_dir == Path("/tmp/custom-activities")


@pytest.mark.parametrize(("value", "expected"), [(None, True), ("true", True), ("false", False)])
def test_coach_worker_enabled_parses_explicit_boolean(value, expected):
    environ = {} if value is None else {"GARMIN_COACH_WORKER_ENABLED": value}
    assert get_app_config(environ).coach_worker_enabled is expected


def test_coach_worker_enabled_rejects_invalid_value():
    with pytest.raises(ValueError, match="GARMIN_COACH_WORKER_ENABLED"):
        get_app_config({"GARMIN_COACH_WORKER_ENABLED": "sometimes"})
