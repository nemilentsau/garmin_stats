"""Retrieval-first assistant chat orchestration."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from uuid import uuid4

from app.domains.assistant.application.runtime_stream import (
    RuntimeReplyComplete,
    RuntimeReplyDelta,
    stream_runtime_reply,
)
from app.domains.assistant.application.turn_context import prepare_turn_context
from app.domains.assistant.contracts import (
    AssistantMessage,
    AssistantMessageCreateRequest,
    AssistantRun,
    AssistantThread,
)
from app.domains.assistant.dependencies import (
    AssistantConversationStore,
    AssistantReadModelStore,
    AssistantRuntime,
)
from app.utils.timeutil import now_iso


def _json_line(payload: dict[str, object]) -> str:
    return json.dumps(payload) + "\n"


def _model_for_thread(thread: AssistantThread) -> str:
    return thread.model or "sonnet"


def _thread_with_state(
    *,
    thread: AssistantThread,
    last_message_at: str,
    snapshot_id: str | None = None,
    session_id: str | None = None,
) -> AssistantThread:
    updates: dict[str, object] = {"last_message_at": last_message_at}
    if snapshot_id is not None:
        updates["last_context_snapshot_id"] = snapshot_id
    if session_id is not None:
        updates["claude_session_id"] = session_id
    return thread.model_copy(update=updates)


async def stream_reply(
    *,
    repo: AssistantConversationStore,
    read_store: AssistantReadModelStore,
    runtime: AssistantRuntime,
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    run: AssistantRun | None = None

    try:
        thread = repo.get_thread(thread_id)
        if thread is None:
            raise LookupError(f"Assistant thread '{thread_id}' not found")

        prior_messages = repo.list_messages(thread_id)
        user_message = AssistantMessage(
            id=request.id,
            thread_id=thread_id,
            role="user",
            content_markdown=request.content,
            created_at=now_iso(),
        )
        repo.save_message(user_message)

        turn_context = prepare_turn_context(
            recall_store=repo,
            read_store=read_store,
            thread_id=thread.id,
            user_message_id=request.id,
            query=request.content,
        )

        run = AssistantRun(
            id=f"run-{uuid4().hex}",
            task_type="chat",
            status="running",
            thread_id=thread.id,
            context_snapshot_id=turn_context.evidence_bundle.id,
            command_json={
                "model": _model_for_thread(thread),
                "intent": turn_context.route.intent,
                "confidence": turn_context.route.confidence,
                "matched_signals": list(turn_context.route.matched_signals),
            },
            started_at=now_iso(),
        )
        repo.save_run(run)
        repo.save_evidence_bundle(turn_context.evidence_bundle)

        assistant_message: AssistantMessage | None = None
        session_id: str | None = None
        async for event in stream_runtime_reply(
            runtime=runtime,
            evidence_bundle=turn_context.evidence_bundle,
            prior_messages=prior_messages,
            memory_records=turn_context.prompt_memory_records,
            user_message=request.content,
            model=_model_for_thread(thread),
            thread_id=thread_id,
        ):
            if isinstance(event, RuntimeReplyDelta):
                yield _json_line({"type": "delta", "text": event.text})
                continue
            if isinstance(event, RuntimeReplyComplete):
                assistant_message = event.assistant_message
                session_id = event.session_id

        # stream_runtime_reply always emits RuntimeReplyComplete last
        assert assistant_message is not None
        thread = _thread_with_state(
            thread=thread,
            last_message_at=assistant_message.created_at or now_iso(),
            snapshot_id=turn_context.evidence_bundle.id,
            session_id=session_id,
        )
        completed_run = run.model_copy(
            update={
                "status": "completed",
                "claude_session_id": session_id,
                "finished_at": now_iso(),
            }
        )
        repo.finalize_reply(
            assistant_message=assistant_message,
            updated_thread=thread,
            completed_run=completed_run,
            memory_record=turn_context.pending_memory_record,
        )
        yield _json_line(
            {
                "type": "done",
                "message": assistant_message.model_dump(mode="json"),
                "session_id": session_id,
                "snapshot_id": turn_context.evidence_bundle.id,
                "run_id": completed_run.id,
            }
        )
    except Exception as exc:
        if run is not None:
            with suppress(Exception):
                usage_json = dict(run.usage_json)
                usage_json["last_error"] = str(exc)
                repo.save_run(
                    run.model_copy(
                        update={
                            "status": "failed",
                            "stderr_path": None,
                            "usage_json": usage_json,
                            "finished_at": now_iso(),
                        }
                    )
                )
        payload: dict[str, object] = {"type": "error", "message": str(exc)}
        if run is not None:
            payload["run_id"] = run.id
        yield _json_line(payload)
        return
