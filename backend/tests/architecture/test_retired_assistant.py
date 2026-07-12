"""Guard rails for retiring assistant chat while preserving artifact ingress."""

from pathlib import Path

from app.bootstrap.app import create_app
from app.bootstrap.schema import init_storage
from app.infra import sqlite
from tests._architecture import REPO_ROOT, assert_no_repo_imports_of


def _route_paths() -> set[str]:
    return {
        path
        for route in create_app().routes
        if isinstance((path := getattr(route, "path", None)), str)
    }


def test_assistant_chat_router_is_not_registered():
    paths = _route_paths()

    assert not any(path.startswith("/api/assistant/threads") for path in paths)


def test_assistant_domain_is_not_importable_from_active_application_code():
    retired_domain = REPO_ROOT / "backend/app/domains/assistant"
    assert not list(retired_domain.rglob("*.py"))
    assert_no_repo_imports_of(["app.domains.assistant"], caller_file=Path(__file__))


def test_assistant_artifact_routes_remain_registered():
    paths = _route_paths()

    assert "/api/assistant/artifacts" in paths
    assert "/api/assistant/artifact-bundles/preview" in paths
    assert "/api/assistant/artifact-bundles/import" in paths


def test_storage_initialization_does_not_drop_preexisting_retired_tables():
    with sqlite.connect() as connection:
        connection.execute("DROP TABLE IF EXISTS assistant_threads")
        connection.execute(
            "CREATE TABLE assistant_threads (id TEXT PRIMARY KEY, marker TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO assistant_threads (id, marker) VALUES (?, ?)",
            ("sentinel", "preserve-me"),
        )
        connection.commit()

    init_storage()

    with sqlite.connect() as connection:
        row = connection.execute(
            "SELECT marker FROM assistant_threads WHERE id = ?", ("sentinel",)
        ).fetchone()
    assert row is not None
    assert row["marker"] == "preserve-me"
