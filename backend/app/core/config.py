"""Application configuration helpers."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5180",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5180",
]


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    data_dir: Path
    activities_dir: Path
    garmin_token_dir: Path


def get_app_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    """Return filesystem/runtime paths from environment or project defaults."""
    env = os.environ if environ is None else environ
    default_database_path = _PROJECT_ROOT / "storage" / "garmin_stats.db"
    default_data_dir = _PROJECT_ROOT / "data" / "garmin_health_stats"
    default_activities_dir = _PROJECT_ROOT / "data" / "garmin_activities"
    return AppConfig(
        database_path=Path(
            env.get("GARMIN_DB_PATH", str(default_database_path))
        ).expanduser(),
        data_dir=Path(env.get("GARMIN_DATA_DIR", str(default_data_dir))).expanduser(),
        activities_dir=Path(
            env.get("GARMIN_ACTIVITY_DATA_DIR", str(default_activities_dir))
        ).expanduser(),
        garmin_token_dir=Path(
            env.get("GARMINTOKENS", "~/.garminconnect")
        ).expanduser(),
    )


def get_cors_origins() -> list[str]:
    """Return allowed CORS origins from env, or the project defaults."""
    origins_env = os.environ.get("BACKEND_CORS_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    return list(_DEFAULT_CORS_ORIGINS)
