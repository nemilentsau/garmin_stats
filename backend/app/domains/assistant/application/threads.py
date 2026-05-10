"""Thread and message catalog use cases for assistant conversations."""

from __future__ import annotations

from app.domains.assistant.contracts import (
    AssistantMessagesResponse,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)
from app.domains.assistant.dependencies import AssistantConversationStore
from app.utils.timeutil import now_iso


def list_threads(repo: AssistantConversationStore) -> AssistantThreadsResponse:
    """List assistant threads with the most recently active thread first."""
    threads = sorted(
        repo.list_threads(),
        key=lambda thread: thread.last_message_at or thread.created_at or "",
        reverse=True,
    )
    return AssistantThreadsResponse(threads=threads)


def create_thread(
    repo: AssistantConversationStore,
    request: AssistantThreadCreateRequest,
) -> AssistantThread:
    """Create a thread with the caller-selected mode/model and current timestamp."""
    thread = AssistantThread(
        id=request.id,
        title=request.title,
        mode=request.mode,
        model=request.model,
        created_at=now_iso(),
    )
    repo.create_thread(thread)
    return thread


def get_thread(repo: AssistantConversationStore, thread_id: str) -> AssistantThread:
    """Load one assistant thread or raise when it is missing."""
    thread = repo.get_thread(thread_id)
    if thread is None:
        raise LookupError(f"Assistant thread {thread_id} not found")
    return thread


def list_messages(
    repo: AssistantConversationStore,
    thread_id: str,
) -> AssistantMessagesResponse:
    """List messages for an existing assistant thread."""
    get_thread(repo, thread_id)
    return AssistantMessagesResponse(messages=repo.list_messages(thread_id))
