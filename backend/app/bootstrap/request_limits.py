"""ASGI request-size boundaries that must run before JSON body parsing."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_TRAINING_IMPORT_REQUEST_BYTES = 7 * 1024 * 1024


class TrainingImportRequestLimitMiddleware:
    """Reject oversized training-import bodies before FastAPI materializes JSON."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _is_training_import(scope):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_TRAINING_IMPORT_REQUEST_BYTES:
                    await _send_too_large(scope, receive, send)
                    return
            except ValueError:
                pass

        buffered_messages: list[Message] = []
        received_bytes = 0
        while True:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > MAX_TRAINING_IMPORT_REQUEST_BYTES:
                    await _send_too_large(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break

        replay_index = 0

        async def replay_receive() -> Message:
            nonlocal replay_index
            if replay_index < len(buffered_messages):
                message = buffered_messages[replay_index]
                replay_index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, send)


def _is_training_import(scope: Scope) -> bool:
    return (
        scope["type"] == "http"
        and scope.get("method") == "POST"
        and scope.get("path") == "/api/training/import"
    )


async def _send_too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=413,
        content={"detail": "Training import request is too large"},
    )
    await response(scope, receive, send)
