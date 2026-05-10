"""Realtime event bus for pushing server-sent events to connected frontends."""

import asyncio
import logging

log = logging.getLogger(__name__)


class EventBus:
    """Broadcasts SSE-formatted events to all subscribed clients."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def subscribe(self) -> asyncio.Queue[str]:
        """Create a new subscriber queue and register it."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)
        log.info("SSE client connected (%d total)", len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)
        log.info("SSE client disconnected (%d remaining)", len(self._subscribers))

    async def broadcast(self, event: str, data: str = "") -> None:
        """Push an SSE-formatted message to all subscribers, skip full queues."""
        message = f"event: {event}\ndata: {data}\n\n"
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                log.warning("Dropping SSE message for slow client")


# Module-level singleton
event_bus = EventBus()


async def heartbeat_loop() -> None:
    """Send periodic heartbeat events to keep SSE connections alive."""
    while True:
        await asyncio.sleep(30)
        await event_bus.broadcast("heartbeat", "")
