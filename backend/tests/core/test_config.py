"""Tests for shared application configuration."""

from pathlib import Path

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
