"""Assistant HTTP routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..models import (
    AssistantMessageCreateRequest,
    AssistantMessagesResponse,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)
from ..services.assistant import (
    create_thread,
    get_thread,
    list_messages,
    list_threads,
    stream_thread_reply,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/threads", response_model=AssistantThreadsResponse)
def get_threads():
    """Return all assistant threads."""
    return list_threads()


@router.post("/threads", response_model=AssistantThread)
def post_thread(request: AssistantThreadCreateRequest):
    """Create a new assistant thread."""
    return create_thread(request)


@router.get("/threads/{thread_id}", response_model=AssistantThread)
def get_thread_detail(thread_id: str):
    """Return a single assistant thread."""
    try:
        return get_thread(thread_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/threads/{thread_id}/messages", response_model=AssistantMessagesResponse)
def get_thread_messages(thread_id: str):
    """Return the messages for a thread."""
    try:
        return list_messages(thread_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/threads/{thread_id}/messages")
async def post_thread_message(thread_id: str, request: AssistantMessageCreateRequest):
    """Stream an assistant reply as NDJSON."""
    try:
        get_thread(thread_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        stream_thread_reply(thread_id, request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
