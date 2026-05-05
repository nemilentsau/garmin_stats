"""Architecture guard rails for assistant domain ownership."""

from tests._architecture import read_repo_file


def test_assistant_domain_api_does_not_import_flat_service_modules():
    for path in [
        "backend/app/domains/assistant/api/threads.py",
        "backend/app/domains/assistant/api/__init__.py",
    ]:
        source = read_repo_file(path)
        assert "app.services.assistant" not in source
        assert "app.services.assistant_context" not in source
        assert "app.services.assistant_runtime" not in source
        assert "app.routers.assistant" not in source


def test_bootstrap_routing_mounts_domain_assistant_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.assistant.api.threads" in source
    assert "from ..routers.assistant import router as assistant_router" not in source
    assert "include_router(assistant_router)" in source
