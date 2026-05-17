"""SQLite-backed assistant conversation repository.

This module owns assistant conversation persistence, assistant-specific SQLite
migrations, and recall lookup storage. Shared SQLite connection/bootstrap
primitives stay in ``app.infra``; lookup policy derived from assistant domain
text rules stays here.
"""

from __future__ import annotations

import sqlite3

from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantRun,
    AssistantThread,
)
from app.domains.assistant.domain.text import normalize_alias
from app.infra.jsonstore import JsonStore, model_from_row
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({
    "assistant_threads",
    "assistant_messages",
    "assistant_runs",
    "assistant_evidence_bundles",
    "assistant_memory_records",
})


def migrate_assistant_storage() -> None:
    # Alias lookup is derived from assistant text-normalization policy, so the
    # backfill lives here rather than in the global schema bootstrap.
    with connect() as con, con:
        _ensure_memory_alias_lookup_columns(con)


def _ensure_memory_alias_lookup_columns(con: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in con.execute("PRAGMA table_info(assistant_memory_records)").fetchall()
    }
    if "alias_normalized" not in columns:
        con.execute("ALTER TABLE assistant_memory_records ADD COLUMN alias_normalized TEXT")

    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_assistant_memory_records_kind_alias_normalized_created "
        "ON assistant_memory_records (kind, alias_normalized, created_at)"
    )

    rows = con.execute(
        "SELECT id, alias_text FROM assistant_memory_records "
        "WHERE alias_text IS NOT NULL AND (alias_normalized IS NULL OR alias_normalized = '')"
    ).fetchall()
    con.executemany(
        "UPDATE assistant_memory_records SET alias_normalized = ? WHERE id = ?",
        [(normalize_alias(row["alias_text"]), row["id"]) for row in rows],
    )


def create_assistant_thread(thread: AssistantThread) -> None:
    """Insert one new assistant thread and reject duplicate ids."""
    created_at = thread.created_at or now_iso()
    payload = thread.model_copy(update={"created_at": created_at}).model_dump_json()
    with connect() as con, con:
        try:
            con.execute(
                (
                    "INSERT INTO assistant_threads "
                    "(id, data, created_at, updated_at) VALUES (?, ?, ?, ?)"
                ),
                (thread.id, payload, created_at, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Assistant thread {thread.id} already exists") from exc


def load_assistant_thread(thread_id: str) -> AssistantThread | None:
    return _STORE.load("assistant_threads", AssistantThread, thread_id)


def load_assistant_threads() -> list[AssistantThread]:
    return _STORE.load_many("assistant_threads", AssistantThread)


def _save_assistant_message_in_connection(
    con: sqlite3.Connection,
    message: AssistantMessage,
) -> None:
    _STORE.save_in_connection(
        con,
        "assistant_messages",
        message.id,
        message.model_dump_json(),
        extra_columns={"thread_id": message.thread_id},
        created_at=message.created_at,
    )


def _touch_thread_activity_in_connection(
    con: sqlite3.Connection,
    *,
    thread_id: str,
    last_message_at: str,
) -> None:
    row = con.execute(
        "SELECT data, created_at, updated_at FROM assistant_threads WHERE id = ?",
        (thread_id,),
    ).fetchone()
    if row is None:
        return
    thread = model_from_row(AssistantThread, row)
    updated_thread = thread.model_copy(update={"last_message_at": last_message_at})
    _STORE.save_in_connection(
        con,
        "assistant_threads",
        updated_thread.id,
        updated_thread.model_dump_json(),
    )


def _save_assistant_message_and_touch_thread(message: AssistantMessage) -> None:
    """Persist a message and advance the owning thread's activity timestamp."""
    with connect() as con, con:
        _save_assistant_message_in_connection(con, message)
        _touch_thread_activity_in_connection(
            con,
            thread_id=message.thread_id,
            last_message_at=message.created_at or now_iso(),
        )


def load_assistant_messages(thread_id: str) -> list[AssistantMessage]:
    return _STORE.load_many(
        "assistant_messages",
        AssistantMessage,
        where_sql="thread_id = ?",
        params=(thread_id,),
        order_by="created_at, id",
    )


def save_assistant_run(run: AssistantRun) -> None:
    _STORE.save(
        "assistant_runs",
        run.id,
        run.model_dump_json(),
        extra_columns={"thread_id": run.thread_id},
        created_at=run.started_at,
        updated_at=run.finished_at or run.started_at,
    )


def _memory_record_columns(record: AssistantMemoryRecord) -> dict[str, object | None]:
    return {
        "kind": record.kind,
        "entity_id": record.entity_id,
        "alias_text": record.alias_text,
        "alias_normalized": normalize_alias(record.alias_text),
    }


def finalize_assistant_reply(
    *,
    assistant_message: AssistantMessage,
    updated_thread: AssistantThread,
    completed_run: AssistantRun,
    memory_record: AssistantMemoryRecord | None = None,
) -> None:
    """Persist reply message, thread metadata, run state, and optional memory in one transaction."""
    with connect() as con, con:
        _save_assistant_message_in_connection(con, assistant_message)
        _STORE.save_in_connection(
            con,
            "assistant_threads",
            updated_thread.id,
            updated_thread.model_dump_json(),
        )
        _STORE.save_in_connection(
            con,
            "assistant_runs",
            completed_run.id,
            completed_run.model_dump_json(),
            extra_columns={"thread_id": completed_run.thread_id},
            created_at=completed_run.started_at,
            updated_at=completed_run.finished_at or completed_run.started_at,
        )
        if memory_record is not None:
            _STORE.save_in_connection(
                con,
                "assistant_memory_records",
                memory_record.id,
                memory_record.model_dump_json(),
                extra_columns=_memory_record_columns(memory_record),
                created_at=memory_record.created_at,
                updated_at=memory_record.updated_at or memory_record.created_at,
            )


def save_assistant_evidence_bundle(bundle: AssistantEvidenceBundle) -> None:
    _STORE.save(
        "assistant_evidence_bundles",
        bundle.id,
        bundle.model_dump_json(),
        extra_columns={
            "thread_id": bundle.thread_id,
            "user_message_id": bundle.user_message_id,
            "intent": bundle.intent,
        },
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
    )


def load_assistant_evidence_bundles(
    thread_id: str | None = None,
    *,
    last_n: int | None = None,
) -> list[AssistantEvidenceBundle]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _STORE.load_many(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
        last_n=last_n,
    )


def load_assistant_evidence_bundles_excluding_thread(
    thread_id: str,
    *,
    last_n: int | None = None,
) -> list[AssistantEvidenceBundle]:
    return _STORE.load_many(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql="thread_id != ?",
        params=(thread_id,),
        order_by="created_at, id",
        last_n=last_n,
    )


def load_assistant_memory_records(
    kind: str | None = None,
    *,
    last_n: int | None = None,
    alias_candidates: tuple[str, ...] | None = None,
) -> list[AssistantMemoryRecord]:
    clauses: list[str] = []
    params: list[object] = []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)

    normalized_candidates = tuple(
        normalized
        for normalized in (
            normalize_alias(candidate) for candidate in (alias_candidates or ())
        )
        if normalized is not None
    )
    if alias_candidates is not None:
        if not normalized_candidates:
            return []
        placeholders = ", ".join("?" for _ in normalized_candidates)
        clauses.append(f"alias_normalized IN ({placeholders})")
        params.extend(normalized_candidates)

    return _STORE.load_many(
        "assistant_memory_records",
        AssistantMemoryRecord,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="created_at, id",
        last_n=last_n,
    )


class SqliteAssistantRepository:
    """Conversation and recall storage adapter wired by bootstrap."""

    def list_threads(self) -> list[AssistantThread]:
        return load_assistant_threads()

    def get_thread(self, thread_id: str) -> AssistantThread | None:
        return load_assistant_thread(thread_id)

    def create_thread(self, thread: AssistantThread) -> None:
        create_assistant_thread(thread)

    def list_messages(self, thread_id: str) -> list[AssistantMessage]:
        return load_assistant_messages(thread_id)

    def save_message(self, message: AssistantMessage) -> None:
        _save_assistant_message_and_touch_thread(message)

    def finalize_reply(
        self,
        *,
        assistant_message: AssistantMessage,
        updated_thread: AssistantThread,
        completed_run: AssistantRun,
        memory_record: AssistantMemoryRecord | None = None,
    ) -> None:
        finalize_assistant_reply(
            assistant_message=assistant_message,
            updated_thread=updated_thread,
            completed_run=completed_run,
            memory_record=memory_record,
        )

    def save_run(self, run: AssistantRun) -> None:
        save_assistant_run(run)

    def save_evidence_bundle(self, bundle: AssistantEvidenceBundle) -> None:
        save_assistant_evidence_bundle(bundle)

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]:
        return load_assistant_evidence_bundles(thread_id=thread_id, last_n=last_n)

    def list_evidence_bundles_excluding_thread(
        self,
        thread_id: str,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]:
        return load_assistant_evidence_bundles_excluding_thread(
            thread_id=thread_id,
            last_n=last_n,
        )

    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
        alias_candidates: tuple[str, ...] | None = None,
    ) -> list[AssistantMemoryRecord]:
        return load_assistant_memory_records(
            kind=kind,
            last_n=last_n,
            alias_candidates=alias_candidates,
        )
