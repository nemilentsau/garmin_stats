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
        "backend/app/domains/assistant/application/memory_aliases.py",
        "backend/app/domains/assistant/application/threads.py",
    ])


def test_assistant_domain_modules_do_not_import_runtime_or_dependencies():
    assert_no_text_in_files(
        [
            "backend/app/domains/assistant/domain/current_state.py",
            "backend/app/domains/assistant/domain/experiment_evidence.py",
            "backend/app/domains/assistant/domain/payloads.py",
            "backend/app/domains/assistant/domain/text.py",
        ],
        [
            "fastapi",
            "app.infra",
            "app.services",
            "app.routers",
            "app.domains.assistant.adapters",
            "app.domains.assistant.application",
            "app.domains.assistant.dependencies",
            "app.domains.assistant.runtime",
            "build_container",
        ],
    )


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
        "backend/app/domains/assistant/domain/current_state.py",
        "backend/app/domains/assistant/domain/experiment_evidence.py",
        "backend/app/domains/assistant/domain/payloads.py",
        "backend/app/domains/assistant/runtime.py",
    ]:
        assert (REPO_ROOT / path).exists()


def test_assistant_sqlite_adapter_is_the_database_boundary():
    source = read_repo_file("backend/app/domains/assistant/adapters.py")

    assert "app.infra.database" not in source
    assert "app.infra.jsonstore" in source
    assert "class SqliteAssistantRepository" in source
    assert "def finalize_assistant_reply(" in source
    assert "app.domains.routines.adapters" not in source
    assert "app.domains.garmin_analytics.adapters" not in source
    assert "app.domains.journal.adapters" not in source
    assert "app.domains.routines.dependencies" in source
    assert "app.domains.garmin_analytics.application.dependencies" in source
    assert "app.domains.journal.dependencies" in source


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


def test_assistant_alias_migration_lives_with_sqlite_adapter():
    database_source = read_repo_file("backend/app/infra/database.py")
    adapter_source = read_repo_file("backend/app/domains/assistant/adapters.py")
    lifespan_source = read_repo_file("backend/app/bootstrap/lifespan.py")

    assert "_ensure_assistant_memory_alias_lookup_columns" not in database_source
    assert "_normalize_alias_text" not in database_source
    assert "idx_assistant_memory_records_kind_alias_normalized_created" not in database_source
    assert "def migrate_assistant_storage(" in adapter_source
    assert "normalize_alias(row" in adapter_source
    assert "migrate_assistant_storage()" in lifespan_source


def test_assistant_application_does_not_import_storage_adapters_or_runtime():
    assert_no_text_in_files(
        [
            "backend/app/domains/assistant/dependencies.py",
            "backend/app/domains/assistant/application/chat.py",
            "backend/app/domains/assistant/application/entity_resolution.py",
            "backend/app/domains/assistant/application/evidence.py",
            "backend/app/domains/assistant/application/retrieval.py",
            "backend/app/domains/assistant/application/intent_routing.py",
            "backend/app/domains/assistant/application/memory_aliases.py",
            "backend/app/domains/assistant/application/threads.py",
        ],
        [
            "app.domains.assistant.adapters",
            "app.domains.assistant.runtime",
        ],
    )


def test_assistant_chat_uses_contract_models_for_thread_state():
    assert_no_text_in_files(
        [
            "backend/app/domains/assistant/application/chat.py",
            "backend/app/domains/assistant/dependencies.py",
            "backend/app/domains/assistant/adapters.py",
        ],
        [
            "_RetrievalStoreAdapter",
            "_message_to_dict",
            "AssistantRetrievalStore",
            "AssistantThread | dict",
            "isinstance(thread, dict)",
            "isinstance(updated_thread, dict)",
        ],
    )


def test_assistant_chat_delegates_memory_alias_policy():
    chat_source = read_repo_file("backend/app/domains/assistant/application/chat.py")
    memory_alias_path = (
        REPO_ROOT / "backend/app/domains/assistant/application/memory_aliases.py"
    )

    assert memory_alias_path.exists()
    memory_alias_source = memory_alias_path.read_text(encoding="utf-8")
    assert "application.memory_aliases import" in chat_source
    assert "resolve_entities(" not in memory_alias_source

    delegated_policy = [
        "_QUESTION_WORDS",
        "_alias_query_candidates",
        "_query_contains_alias",
    ]
    assert [policy for policy in delegated_policy if policy in chat_source] == []
    assert [policy for policy in delegated_policy if policy not in memory_alias_source] == []


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
