"""Regression guards for the retired v2 routine and artifact runtime."""

from tests._architecture import REPO_ROOT, read_repo_file


def test_v2_routine_and_artifact_sources_are_absent():
    for path in [
        "backend/app/domains/routines",
        "backend/app/domains/artifacts",
        "backend/tests/domains/routines",
        "backend/tests/domains/artifacts",
        "backend/tests/_routines_helpers.py",
        "backend/tests/_artifacts_helpers.py",
        "docs/routine_bundles",
        "scripts/import_bundles.py",
    ]:
        assert not (REPO_ROOT / path).exists(), path


def test_v2_runtime_is_absent_from_app_composition():
    sources = {
        path: read_repo_file(path)
        for path in [
            "backend/app/bootstrap/container.py",
            "backend/app/bootstrap/routing.py",
            "backend/app/bootstrap/schema.py",
        ]
    }

    for source in sources.values():
        assert "app.domains.routines" not in source
        assert "app.domains.artifacts" not in source

    container = sources["backend/app/bootstrap/container.py"]
    assert "routines_repo" not in container
    assert "artifacts_repo" not in container


def test_v2_storage_tables_are_explicitly_retired():
    schema = read_repo_file("backend/app/bootstrap/schema.py")

    for table in [
        "assistant_artifacts",
        "card_templates",
        "routines",
        "routine_entries",
        "routine_schedules",
        "routine_assignments",
        "card_logs",
        "card_overrides",
    ]:
        assert f'"{table}"' in schema


def test_generated_contracts_do_not_publish_v2_routes():
    generated = read_repo_file("frontend/src/lib/api-types.ts")
    routes = read_repo_file("docs/reference/routes.md")

    for prefix in [
        "/api/today",
        "/api/routines",
        "/api/cards",
        "/api/assistant/artifact",
    ]:
        assert f'"{prefix}' not in generated
        assert f"`{prefix}" not in routes
