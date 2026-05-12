"""HTTP routes for assistant threads and streaming replies.

Routes keep FastAPI and NDJSON streaming details at the assistant boundary,
resolve the app container, and delegate thread lifecycle and chat orchestration
to application use cases.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.bootstrap.container import build_container
from app.domains.assistant.application.chat import stream_reply
from app.domains.assistant.application.threads import (
    create_thread,
    get_thread,
    list_messages,
    list_threads,
)
from app.domains.assistant.contracts import (
    AssistantMessageCreateRequest,
    AssistantMessagesResponse,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/threads", response_model=AssistantThreadsResponse)
def get_threads():
    """Return all assistant threads ordered by recent activity."""
    return list_threads(build_container().assistant_repo)


@router.post("/threads", response_model=AssistantThread)
def post_thread(request: AssistantThreadCreateRequest):
    """Create one assistant thread."""
    return create_thread(build_container().assistant_repo, request)


@router.get("/threads/{thread_id}", response_model=AssistantThread)
def get_thread_detail(thread_id: str):
    """Return one assistant thread or raise when it is missing."""
    return get_thread(build_container().assistant_repo, thread_id)


@router.get("/threads/{thread_id}/messages", response_model=AssistantMessagesResponse)
def get_thread_messages(thread_id: str):
    """Return messages for one existing assistant thread."""
    return list_messages(build_container().assistant_repo, thread_id)


@router.post("/threads/{thread_id}/messages")
async def post_thread_message(thread_id: str, request: AssistantMessageCreateRequest):
    """Persist a user message and stream the assistant reply as NDJSON."""
    container = build_container()
    repository = container.assistant_repo
    get_thread(repository, thread_id)
    return StreamingResponse(
        stream_reply(
            repo=repository,
            read_store=repository,
            runtime=container.assistant_runtime,
            thread_id=thread_id,
            request=request,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
