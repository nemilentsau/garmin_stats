"""Architecture guard rails for assistant domain ownership."""

from tests._architecture import (
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    read_repo_file,
)


def test_assistant_domain_api_does_not_import_flat_service_modules():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/assistant/api/threads.py",
        "backend/app/domains/assistant/api/__init__.py",
    ])


def test_assistant_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/assistant/application/chat.py",
        "backend/app/domains/assistant/application/entity_resolution.py",
        "backend/app/domains/assistant/application/evidence.py",
        "backend/app/domains/assistant/application/ports.py",
        "backend/app/domains/assistant/application/retrieval.py",
        "backend/app/domains/assistant/application/router.py",
        "backend/app/domains/assistant/application/threads.py",
        "backend/app/domains/assistant/application/types.py",
    ])


def test_bootstrap_routing_mounts_domain_assistant_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.assistant.api.threads" in source
    assert "from ..routers.assistant import router as assistant_router" not in source
    assert "include_router(assistant_router)" in source
