"""Routine API tests."""

import asyncio

from fastapi import FastAPI
from starlette.types import Message

import app.domains.routines.routes as routines_api_mod
from app.domains.routines.contracts import ScheduleWindow


async def _today_status(method: str, path: str) -> int:
    app = FastAPI()
    app.include_router(routines_api_mod.today_router)

    messages: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
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
    return int(start["status"])  # type: ignore[arg-type]


class TestRoutineApi:
    def test_get_schedule_window_returns_projection(self, monkeypatch):
        monkeypatch.setattr(
            routines_api_mod,
            "get_schedule_window",
            lambda *_args, **_kwargs: ScheduleWindow(
                start_date="2026-03-02", end_date="2026-03-15"
            ),
        )

        window = routines_api_mod.get_routine_schedule_window("2026-03-02")

        assert window.start_date == "2026-03-02"
        assert window.end_date == "2026-03-15"

    def test_post_today_cards_returns_404(self):
        status = asyncio.run(_today_status("POST", "/api/today/2026-03-02/cards"))

        assert status == 404

    def test_delete_today_card_returns_405(self):
        status = asyncio.run(
            _today_status(
                "DELETE",
                "/api/today/2026-03-02/cards/scheduled:assignment-1:2026-03-02",
            )
        )

        assert status == 405
