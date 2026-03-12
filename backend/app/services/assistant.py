"""Assistant service orchestration."""

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from uuid import uuid4

from ..infra.database import (
    load_assistant_messages,
    load_assistant_runs,
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
from .assistant_context import build_context_snapshot
from .assistant_runtime import ClaudeCodeRuntime

_runtime = ClaudeCodeRuntime()


def list_threads() -> AssistantThreadsResponse:
    threads = sorted(
        load_assistant_threads(),
        key=lambda thread: thread.last_message_at or thread.created_at or "",
        reverse=True,
    )
    return AssistantThreadsResponse(threads=threads, total=len(threads))


def create_thread(request: AssistantThreadCreateRequest) -> AssistantThread:
    thread = AssistantThread(
        id=request.id,
        title=request.title,
        mode=request.mode,
        model=request.model,
        created_at=datetime.now(UTC).isoformat(),
    )
    save_assistant_thread(thread)
    return thread


def get_thread(thread_id: str) -> AssistantThread:
    for thread in load_assistant_threads():
        if thread.id == thread_id:
            return thread
    raise LookupError(f"Assistant thread {thread_id} not found")


def list_messages(thread_id: str) -> AssistantMessagesResponse:
    get_thread(thread_id)
    messages = load_assistant_messages(thread_id)
    return AssistantMessagesResponse(messages=messages, total=len(messages))


def _save_thread_update(thread: AssistantThread) -> None:
    save_assistant_thread(thread)


def _replace_thread(
    thread: AssistantThread,
    *,
    claude_session_id: str | None = None,
    last_context_snapshot_id: str | None = None,
    last_message_at: str | None = None,
) -> AssistantThread:
    return AssistantThread(
        id=thread.id,
        title=thread.title,
        mode=thread.mode,
        model=thread.model,
        claude_session_id=(
            claude_session_id
            if claude_session_id is not None
            else thread.claude_session_id
        ),
        last_context_snapshot_id=(
            last_context_snapshot_id
            if last_context_snapshot_id is not None
            else thread.last_context_snapshot_id
        ),
        status=thread.status,
        last_message_at=last_message_at if last_message_at is not None else thread.last_message_at,
        created_at=thread.created_at,
    )


async def stream_thread_reply(
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    thread = get_thread(thread_id)
    now = datetime.now(UTC).isoformat()
    user_message = AssistantMessage(
        id=request.id,
        thread_id=thread_id,
        role="user",
        content_markdown=request.content,
        created_at=now,
    )
    save_assistant_message(user_message)
    thread = _replace_thread(thread, last_message_at=now)
    _save_thread_update(thread)

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
                assistant_chunks.append(event["text"])
                await event_bus.broadcast(
                    "assistant_stream_delta",
                    json.dumps({"thread_id": thread_id, "run_id": run.id, "delta": event["text"]}),
                )
                yield json.dumps(event) + "\n"
                continue

            session_id = event.get("session_id")
            assistant_message = AssistantMessage(
                id=assistant_message_id,
                thread_id=thread_id,
                role="assistant",
                content_markdown="".join(assistant_chunks).strip(),
                created_at=datetime.now(UTC).isoformat(),
            )
            save_assistant_message(assistant_message)

            updated_thread = _replace_thread(
                thread,
                claude_session_id=session_id,
                last_context_snapshot_id=snapshot.id,
                last_message_at=assistant_message.created_at,
            )
            _save_thread_update(updated_thread)

            completed_run = AssistantRun(
                id=run.id,
                task_type=run.task_type,
                status="completed",
                thread_id=run.thread_id,
                context_snapshot_id=run.context_snapshot_id,
                claude_session_id=session_id,
                command_json=run.command_json,
                stdout_path=run.stdout_path,
                stderr_path=run.stderr_path,
                usage_json=run.usage_json,
                started_at=run.started_at,
                finished_at=datetime.now(UTC).isoformat(),
            )
            save_assistant_run(completed_run)
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
        failed_run = AssistantRun(
            id=run.id,
            task_type=run.task_type,
            status="failed",
            thread_id=run.thread_id,
            context_snapshot_id=run.context_snapshot_id,
            claude_session_id=run.claude_session_id,
            command_json=run.command_json,
            stderr_path=str(exc),
            started_at=run.started_at,
            finished_at=datetime.now(UTC).isoformat(),
        )
        with suppress(Exception):
            save_assistant_run(failed_run)
        with suppress(Exception):
            await event_bus.broadcast(
                "assistant_run_failed",
                json.dumps({"thread_id": thread_id, "run_id": run.id, "error": str(exc)}),
            )
        yield json.dumps({"type": "error", "message": str(exc), "run_id": run.id}) + "\n"


def list_runs(thread_id: str | None = None) -> list[AssistantRun]:
    return load_assistant_runs(thread_id)
