"""Architecture guard rails for assistant domain ownership."""

from pathlib import Path

from tests._architecture import (
    REPO_ROOT,
    assert_api_modules_are_boundary_only,
    assert_application_modules_are_strict,
    assert_no_repo_imports_of,
    assert_no_text_in_files,
    read_repo_file,
)


def test_assistant_route_module_does_not_import_flat_database_or_services():
    assert_api_modules_are_boundary_only([
        "backend/app/domains/assistant/routes.py",
    ])


def test_assistant_application_modules_follow_strict_boundary():
    assert_application_modules_are_strict([
        "backend/app/domains/assistant/dependencies.py",
        "backend/app/domains/assistant/application/chat.py",
        "backend/app/domains/assistant/application/entity_resolution.py",
        "backend/app/domains/assistant/application/evidence.py",
        "backend/app/domains/assistant/application/retrieval.py",
        "backend/app/domains/assistant/application/intent_routing.py",
        "backend/app/domains/assistant/application/threads.py",
    ])


def test_assistant_uses_flat_capability_layout():
    for path in [
        "backend/app/domains/assistant/api",
        "backend/app/domains/assistant/infra",
        "backend/app/domains/assistant/application/ports.py",
        "backend/app/domains/assistant/application/router.py",
        "backend/app/domains/assistant/application/types.py",
    ]:
        assert not (REPO_ROOT / path).exists()

    for path in [
        "backend/app/domains/assistant/routes.py",
        "backend/app/domains/assistant/adapters.py",
        "backend/app/domains/assistant/dependencies.py",
        "backend/app/domains/assistant/runtime.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_assistant_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/assistant/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteAssistantRepository" in source
    assert "def finalize_assistant_reply(" in source


def test_bootstrap_routing_mounts_domain_assistant_router_directly():
    source = read_repo_file("backend/app/bootstrap/routing.py")
    assert "domains.assistant.routes" in source
    assert "domains.assistant.api.threads" not in source
    assert "from ..routers.assistant import router as assistant_router" not in source
    assert "include_router(assistant_router)" in source


def test_assistant_routes_use_container_repository_and_runtime():
    source = read_repo_file("backend/app/domains/assistant/routes.py")

    assert "build_container" in source
    assert "assistant_repo" in source
    assert "assistant_runtime" in source


def test_shared_database_does_not_own_assistant_contracts_or_crud():
    source = read_repo_file("backend/app/infra/database.py")
    assert "domains.assistant.contracts" not in source
    assert "domains.assistant.application.types" not in source

    assistant_persistence_functions = [
        "def create_assistant_thread(",
        "def save_assistant_thread(",
        "def load_assistant_thread(",
        "def load_assistant_threads(",
        "def save_assistant_message(",
        "def load_assistant_messages(",
        "def save_assistant_run(",
        "def finalize_assistant_reply(",
        "def load_assistant_runs(",
        "def save_assistant_evidence_bundle(",
        "def load_assistant_evidence_bundles(",
        "def save_assistant_memory_record(",
        "def load_assistant_memory_records(",
        "def save_context_snapshot(",
        "def load_context_snapshot(",
        "def load_context_snapshots(",
        "def save_evidence_card(",
        "def load_evidence_cards(",
        "def save_plan(",
        "def load_plans(",
        "def save_plan_item(",
        "def load_plan_items(",
    ]
    assert [name for name in assistant_persistence_functions if name in source] == []


def test_assistant_application_does_not_import_storage_adapters_or_runtime():
    assert_no_text_in_files(
        [
            "backend/app/domains/assistant/dependencies.py",
            "backend/app/domains/assistant/application/chat.py",
            "backend/app/domains/assistant/application/entity_resolution.py",
            "backend/app/domains/assistant/application/evidence.py",
            "backend/app/domains/assistant/application/retrieval.py",
            "backend/app/domains/assistant/application/intent_routing.py",
            "backend/app/domains/assistant/application/threads.py",
        ],
        [
            "app.domains.assistant.adapters",
            "app.domains.assistant.runtime",
        ],
    )


def test_migrated_assistant_router_and_adapter_shims_are_removed():
    for path in [
        "backend/app/domains/assistant/api",
        "backend/app/domains/assistant/infra",
        "backend/app/domains/assistant/application/ports.py",
        "backend/app/domains/assistant/application/router.py",
        "backend/app/domains/assistant/application/types.py",
        "backend/app/routers/assistant.py",
    ]:
        assert not (REPO_ROOT / path).exists()


def test_backend_code_does_not_import_migrated_assistant_paths():
    assert_no_repo_imports_of(
        [
            "app.domains.assistant.api",
            "app.domains.assistant.infra",
            "app.domains.assistant.application.ports",
            "app.domains.assistant.application.router",
            "app.domains.assistant.application.types",
            "app.routers.assistant",
        ],
        Path(__file__),
    )
