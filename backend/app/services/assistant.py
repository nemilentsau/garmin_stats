"""Assistant service orchestration."""

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from uuid import uuid4

from ..infra.database import (
    load_assistant_messages,
    load_assistant_runs,
    load_assistant_thread,
    load_assistant_threads,
    save_assistant_message,
    save_assistant_run,
    save_assistant_thread,
)
from ..infra.events import event_bus
from ..models import (
    AssistantMessage,
    AssistantMessageCreateRequest,
    AssistantMessagesResponse,
    AssistantRun,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)
from ..utils.timeutil import now_iso
from .assistant_context import build_context_snapshot
from .assistant_runtime import ClaudeCodeRuntime

_runtime = ClaudeCodeRuntime()


def list_threads() -> AssistantThreadsResponse:
    threads = sorted(
        load_assistant_threads(),
        key=lambda thread: thread.last_message_at or thread.created_at or "",
        reverse=True,
    )
    return AssistantThreadsResponse(threads=threads)


def create_thread(request: AssistantThreadCreateRequest) -> AssistantThread:
    thread = AssistantThread(
        id=request.id,
        title=request.title,
        mode=request.mode,
        model=request.model,
        created_at=now_iso(),
    )
    save_assistant_thread(thread)
    return thread


def get_thread(thread_id: str) -> AssistantThread:
    thread = load_assistant_thread(thread_id)
    if thread is None:
        raise LookupError(f"Assistant thread {thread_id} not found")
    return thread


def list_messages(thread_id: str) -> AssistantMessagesResponse:
    get_thread(thread_id)
    messages = load_assistant_messages(thread_id)
    return AssistantMessagesResponse(messages=messages)


def _update_thread(
    thread: AssistantThread,
    **updates: str | None,
) -> AssistantThread:
    """Apply non-None updates to a thread and persist."""
    updated = thread.model_copy(update={k: v for k, v in updates.items() if v is not None})
    save_assistant_thread(updated)
    return updated


async def stream_thread_reply(
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    thread = get_thread(thread_id)
    now = now_iso()
    user_message = AssistantMessage(
        id=request.id,
        thread_id=thread_id,
        role="user",
        content_markdown=request.content,
        created_at=now,
    )
    save_assistant_message(user_message)
    thread = _update_thread(thread, last_message_at=now)

    run = AssistantRun(
        id=f"run-{uuid4().hex}",
        task_type="chat",
        status="running",
        thread_id=thread_id,
        claude_session_id=thread.claude_session_id,
        started_at=now,
        command_json={
            "thread_mode": thread.mode,
            "model": thread.model,
        },
    )

    assistant_chunks: list[str] = []
    assistant_message_id = f"assistant-{uuid4().hex}"
    snapshot = None
    try:
        snapshot = build_context_snapshot()
        run.context_snapshot_id = snapshot.id
        save_assistant_run(run)
        await event_bus.broadcast(
            "assistant_run_started",
            json.dumps({"thread_id": thread_id, "run_id": run.id, "snapshot_id": snapshot.id}),
        )

        async for event in _runtime.stream_chat(
            snapshot=snapshot,
            user_message=request.content,
            model=thread.model,
            session_id=thread.claude_session_id,
        ):
            if event["type"] == "delta":
                text = event.get("text")
                if not isinstance(text, str):
                    continue
                assistant_chunks.append(text)
                await event_bus.broadcast(
                    "assistant_stream_delta",
                    json.dumps({"thread_id": thread_id, "run_id": run.id, "delta": text}),
                )
                yield json.dumps(event) + "\n"
                continue

            session_id = event.get("session_id")
            assistant_message = AssistantMessage(
                id=assistant_message_id,
                thread_id=thread_id,
                role="assistant",
                content_markdown="".join(assistant_chunks).strip(),
                created_at=now_iso(),
            )
            save_assistant_message(assistant_message)

            _update_thread(
                thread,
                claude_session_id=session_id,
                last_context_snapshot_id=snapshot.id,
                last_message_at=assistant_message.created_at,
            )

            save_assistant_run(run.model_copy(update={
                "status": "completed",
                "claude_session_id": session_id,
                "finished_at": now_iso(),
            }))
            await event_bus.broadcast(
                "assistant_run_completed",
                json.dumps(
                    {
                        "thread_id": thread_id,
                        "run_id": run.id,
                        "snapshot_id": snapshot.id,
                        "session_id": session_id,
                    }
                ),
            )
            yield json.dumps(
                {
                    "type": "done",
                    "message": assistant_message.model_dump(),
                    "session_id": session_id,
                    "snapshot_id": snapshot.id,
                    "run_id": run.id,
                }
            ) + "\n"
    except Exception as exc:
        with suppress(Exception):
            save_assistant_run(run.model_copy(update={
                "status": "failed",
                "stderr_path": str(exc),
                "finished_at": now_iso(),
            }))
        with suppress(Exception):
            await event_bus.broadcast(
                "assistant_run_failed",
                json.dumps({"thread_id": thread_id, "run_id": run.id, "error": str(exc)}),
            )
        yield json.dumps({"type": "error", "message": str(exc), "run_id": run.id}) + "\n"


def list_runs(thread_id: str | None = None) -> list[AssistantRun]:
    return load_assistant_runs(thread_id)
