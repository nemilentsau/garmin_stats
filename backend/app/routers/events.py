"""SSE events HTTP route."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..infra.events import event_bus

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def sse_events(request: Request):
    """Server-Sent Events stream for real-time data updates."""
    queue = event_bus.subscribe()

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except TimeoutError:
                    continue
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
