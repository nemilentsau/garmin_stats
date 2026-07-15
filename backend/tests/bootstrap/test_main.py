"""Application-level middleware and exception handler tests."""

import asyncio
import json

from starlette.types import Message

import app.main as main_mod

app = main_mod.app


async def _asgi_request(
    path: str,
    *,
    method: str = "GET",
) -> tuple[int, dict[str, str], bytes]:
    """Perform a raw ASGI request and return (status, headers, body)."""
    if "?" in path:
        path_part, qs = path.split("?", 1)
    else:
        path_part, qs = path, ""
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
            "method": method,
            "scheme": "http",
            "path": path_part,
            "raw_path": path_part.encode(),
            "query_string": qs.encode(),
            "root_path": "",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    headers = {
        key.decode(): value.decode()
        for key, value in start["headers"]  # type: ignore[index]
    }
    body_parts = [
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    ]
    return int(start["status"]), headers, b"".join(body_parts)  # type: ignore[arg-type]


async def _response_headers(path: str) -> dict[str, str]:
    _status, headers, _body = await _asgi_request(path)
    return headers


class TestCacheHeaders:
    def test_api_routes_send_no_store_headers(self):
        headers = asyncio.run(_response_headers("/api/dashboard"))

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


class TestExceptionHandlers:
    def test_lookup_error_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.domains.garmin_analytics.routes.load_dashboard_overview",
            lambda *_args: (_ for _ in ()).throw(LookupError("No dashboard data")),
        )

        status, _headers, body = asyncio.run(_asgi_request("/api/dashboard"))

        assert status == 404
        assert json.loads(body)["detail"] == "No dashboard data"

    def test_value_error_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.domains.training.routes.get_training_schedule_window",
            lambda *_args, **_kwargs: (
                _ for _ in ()
            ).throw(ValueError("duration_days must be > 0")),
        )

        status, _headers, body = asyncio.run(
            _asgi_request("/api/training/schedule-window?start=2026-03-02&days=1")
        )

        assert status == 400
        assert json.loads(body)["detail"] == "duration_days must be > 0"
