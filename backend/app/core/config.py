"""Application configuration helpers."""

import os

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


def get_cors_origins() -> list[str]:
    """Return allowed CORS origins from env, or the project defaults."""
    origins_env = os.environ.get("BACKEND_CORS_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    return list(_DEFAULT_CORS_ORIGINS)
