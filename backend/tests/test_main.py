"""Application-level middleware tests."""

import asyncio

from starlette.types import Message

from app.main import app


async def _response_headers(path: str) -> dict[str, str]:
    messages: list[Message] = []
    receive_calls = 0

    async def receive() -> Message:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls == 1:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    return {
        key.decode(): value.decode()
        for key, value in start["headers"]  # type: ignore[index]
    }


class TestCacheHeaders:
    def test_api_routes_send_no_store_headers(self):
        headers = asyncio.run(_response_headers("/api/days"))

        assert headers["cache-control"] == "no-store"
        assert headers["pragma"] == "no-cache"

    def test_non_api_routes_keep_default_cache_headers(self):
        headers = asyncio.run(_response_headers("/"))

        assert "cache-control" not in headers
        assert "pragma" not in headers

    def test_existing_route_cache_policy_is_preserved(self):
        headers = asyncio.run(_response_headers("/api/events"))

        assert headers["cache-control"] == "no-cache"
        assert "pragma" not in headers
