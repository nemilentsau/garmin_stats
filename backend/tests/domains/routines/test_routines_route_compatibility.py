"""Regression tests for routines route contracts."""

import asyncio
import json

from starlette.types import Message

import app.main as main_mod

app = main_mod.app


async def _asgi_request(path: str) -> tuple[int, bytes]:
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
            "method": "GET",
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
    body_parts = [
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    ]
    return int(start["status"]), b"".join(body_parts)  # type: ignore[arg-type]


def test_monkeypatching_domain_routines_api_changes_live_http_behavior(monkeypatch):
    monkeypatch.setattr(
        "app.domains.routines.routes.get_schedule_window",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("domain route patch hit")),
    )

    status, body = asyncio.run(
        _asgi_request("/api/routines/schedule-window?start_date=2026-03-02")
    )

    assert status == 400
    assert json.loads(body)["detail"] == "domain route patch hit"


def test_today_card_logs_openapi_metadata_stays_compatible():
    operation = app.openapi()["paths"]["/api/today/card-logs"]["get"]

    assert operation["operationId"] == "get_card_logs_range_api_today_card_logs_get"
    assert operation["description"] == (
        "Return non-pending card log statuses for schedule-calendar rendering."
    )
