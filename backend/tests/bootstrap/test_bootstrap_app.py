"""Bootstrap app factory tests."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.bootstrap.app import create_app


def test_create_app_returns_configured_fastapi_instance():
    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "Garmin Stats API"
    assert app.description == "API for analyzing Garmin Epix Gen 2 health data"
    assert app.version == "0.1.0"

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/" in paths
    assert "/api/days" not in paths
    assert "/api/days/{date}" not in paths

    assert any(middleware.cls is CORSMiddleware for middleware in app.user_middleware)

    assert LookupError in app.exception_handlers
    assert ValueError in app.exception_handlers
