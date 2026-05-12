"""Assistant adapter tests for SQLite persistence and recall lookup."""

import json

import app.domains.assistant.adapters as assistant_db
import app.infra.database as db
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantResolvedEntity,
    AssistantRun,
    AssistantThread,
)


def _load_run(run_id: str) -> AssistantRun | None:
    with db._connect() as con:
        row = con.execute(
            "SELECT data FROM assistant_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return AssistantRun.model_validate_json(row["data"])


class TestAssistantAdapter:
    def test_migrate_assistant_storage_backfills_legacy_memory_alias_lookup(self):
        with db._connect() as con, con:
            con.execute("DROP TABLE assistant_memory_records")
            con.execute(
                """
                CREATE TABLE assistant_memory_records (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    entity_id TEXT,
                    alias_text TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                INSERT INTO assistant_memory_records (
                    id, kind, entity_id, alias_text, data, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "memory-1",
                    "entity_alias",
                    "exp-1",
                    "Sleep Stack!",
                    json.dumps(
                        {
                            "id": "memory-1",
                            "kind": "entity_alias",
                            "entity_id": "exp-1",
                            "alias_text": "Sleep Stack!",
                            "payload_json": {},
                        }
                    ),
                    "2026-04-11T10:00:00Z",
                    "2026-04-11T10:00:00Z",
                ),
            )

        assistant_db.migrate_assistant_storage()
        assistant_db.migrate_assistant_storage()

        with db._connect() as con:
            columns = {
                row["name"]
                for row in con.execute("PRAGMA table_info(assistant_memory_records)").fetchall()
            }
            indexes = {
                row["name"]
                for row in con.execute("PRAGMA index_list(assistant_memory_records)").fetchall()
            }
            row = con.execute(
                "SELECT alias_normalized FROM assistant_memory_records WHERE id = ?",
                ("memory-1",),
            ).fetchone()

        assert "alias_normalized" in columns
        assert "idx_assistant_memory_records_kind_alias_normalized_created" in indexes
        assert row is not None
        assert row["alias_normalized"] == "sleep stack"

    def test_loader_hydrates_generated_timestamps_from_columns(self):
        assistant_db.save_assistant_thread(AssistantThread(id="thread-1", title="Recovery coach"))
        assistant_db.save_assistant_message(
            AssistantMessage(
                id="message-1",
                thread_id="thread-1",
                role="assistant",
                content_markdown="Sleep dipped last night.",
            )
        )

        messages = assistant_db.load_assistant_messages("thread-1")

        assert messages[0].created_at is not None

    def test_assistant_foundation_records_survive_round_trip(self):
        thread = AssistantThread(
            id="thread-1",
            title="Recovery coach",
            model="opus",
            claude_session_id="session-123",
        )
        message = AssistantMessage(
            id="message-1",
            thread_id="thread-1",
            role="assistant",
            content_markdown="Sleep dipped last night.",
            created_at="2026-01-15T08:00:00+00:00",
        )

        assistant_db.save_assistant_thread(thread)
        assistant_db.save_assistant_message(message)

        threads = assistant_db.load_assistant_threads()
        messages = assistant_db.load_assistant_messages("thread-1")

        assert [entry.id for entry in threads] == ["thread-1"]
        assert [entry.id for entry in messages] == ["message-1"]

    def test_finalize_assistant_reply_persists_message_thread_and_run_state_together(self):
        thread = AssistantThread(
            id="thread-1",
            title="Recovery coach",
            last_message_at="2026-01-14T10:00:00+00:00",
        )
        running_run = AssistantRun(
            id="run-1",
            task_type="chat",
            status="running",
            thread_id="thread-1",
            started_at="2026-01-15T09:00:00+00:00",
        )
        assistant_message = AssistantMessage(
            id="assistant-1",
            thread_id="thread-1",
            role="assistant",
            content_markdown="Keep the bedtime routine consistent.",
            created_at="2026-01-15T09:02:00+00:00",
        )
        updated_thread = thread.model_copy(
            update={
                "claude_session_id": "session-1",
                "last_context_snapshot_id": "bundle-1",
                "last_message_at": assistant_message.created_at,
            }
        )
        completed_run = running_run.model_copy(
            update={
                "status": "completed",
                "context_snapshot_id": "bundle-1",
                "claude_session_id": "session-1",
                "finished_at": "2026-01-15T09:02:01+00:00",
            }
        )
        memory_record = AssistantMemoryRecord(
            id="memory-1",
            kind="entity_alias",
            entity_id="experiment-1",
            alias_text="sleep stack",
            created_at="2026-01-15T09:02:01+00:00",
        )

        assistant_db.create_assistant_thread(thread)
        assistant_db.save_assistant_run(running_run)
        assert assistant_db.load_assistant_messages("thread-1") == []
        loaded_running_run = _load_run("run-1")
        assert loaded_running_run is not None
        assert loaded_running_run.status == "running"

        assistant_db.finalize_assistant_reply(
            assistant_message=assistant_message,
            updated_thread=updated_thread,
            completed_run=completed_run,
            memory_record=memory_record,
        )

        loaded_thread = assistant_db.load_assistant_thread("thread-1")
        loaded_messages = assistant_db.load_assistant_messages("thread-1")
        loaded_memory = assistant_db.load_assistant_memory_records(kind="entity_alias")
        loaded_run = _load_run("run-1")
        with db._connect() as con:
            row = con.execute(
                "SELECT alias_text FROM assistant_memory_records WHERE id = ?",
                ("memory-1",),
            ).fetchone()

        assert loaded_thread is not None
        assert loaded_thread.last_message_at == assistant_message.created_at
        assert loaded_thread.last_context_snapshot_id == "bundle-1"
        assert loaded_thread.claude_session_id == "session-1"
        assert [message.id for message in loaded_messages] == ["assistant-1"]
        assert [record.id for record in loaded_memory] == ["memory-1"]
        assert row is not None
        assert row["alias_text"] == "sleep stack"
        assert loaded_run is not None
        assert loaded_run.id == "run-1"
        assert loaded_run.status == "completed"
        assert loaded_run.finished_at == "2026-01-15T09:02:01+00:00"
        assert loaded_run.context_snapshot_id == "bundle-1"

    def test_assistant_evidence_bundle_round_trips(self):
        bundle = AssistantEvidenceBundle(
            id="bundle-1",
            thread_id="thread-1",
            user_message_id="message-1",
            intent="experiment_review",
            entities=[
                AssistantResolvedEntity(
                    kind="experiment",
                    entity_id="exp-1",
                    label="Meditation -> HRV",
                    score=0.98,
                )
            ],
            items=[
                AssistantEvidenceItem(
                    kind="analysis",
                    source="experiment_analysis",
                    entity_id="exp-1",
                    payload_json={"adherence_rate": 0.5},
                )
            ],
        )

        assistant_db.save_assistant_evidence_bundle(bundle)
        loaded = assistant_db.load_assistant_evidence_bundles(thread_id="thread-1")

        assert loaded[0].intent == "experiment_review"
        assert loaded[0].entities[0].entity_id == "exp-1"

    def test_assistant_memory_record_round_trips(self):
        record = AssistantMemoryRecord(
            id="memory-1",
            kind="entity_alias",
            entity_id="exp-1",
            alias_text="meditation experiment",
            payload_json={"source": "resolver"},
        )

        assistant_db.save_assistant_memory_record(record)
        loaded = assistant_db.load_assistant_memory_records(kind="entity_alias")

        assert loaded[0].alias_text == "meditation experiment"

    def test_assistant_memory_record_alias_lookup_filters_candidates(self):
        assistant_db.save_assistant_memory_record(
            AssistantMemoryRecord(
                id="memory-1",
                kind="entity_alias",
                entity_id="exp-1",
                alias_text="sleep stack",
            )
        )
        assistant_db.save_assistant_memory_record(
            AssistantMemoryRecord(
                id="memory-2",
                kind="entity_alias",
                entity_id="exp-2",
                alias_text="mobility reset",
            )
        )

        loaded = assistant_db.load_assistant_memory_records(
            kind="entity_alias",
            alias_candidates=("sleep stack", "sleep"),
        )

        assert [record.id for record in loaded] == ["memory-1"]
