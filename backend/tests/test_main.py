"""Application-level middleware tests."""

import asyncio

from starlette.types import Message

import app.main as main_mod
from app.models import IngestResult, IngestStatus

app = main_mod.app


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


class TestStartupIngest:
    def test_runs_ingest_after_reconciling_existing_archives(self, monkeypatch):
        order: list[str] = []

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 3

        def fake_check_ingest_status(_data_dir):
            assert order == ["extract"]
            return IngestStatus(
                needs_ingest=True,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=58,
                days_on_disk=72,
            )

        expected = IngestResult(days_ingested=72, duration_ms=321)

        def fake_ingest_all(_data_dir):
            order.append("ingest")
            return expected

        monkeypatch.setattr(main_mod, "extract_existing_archives", fake_extract_existing_archives)
        monkeypatch.setattr(main_mod, "check_ingest_status", fake_check_ingest_status)
        monkeypatch.setattr(main_mod, "ingest_all", fake_ingest_all)

        main_mod._run_startup_ingest_if_needed()

        assert order == ["extract", "ingest"]

    def test_skips_ingest_when_disk_state_matches_database(self, monkeypatch):
        monkeypatch.setattr(main_mod, "extract_existing_archives", lambda _data_dir: 0)
        monkeypatch.setattr(
            main_mod,
            "check_ingest_status",
            lambda _data_dir: IngestStatus(
                needs_ingest=False,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=72,
                days_on_disk=72,
            ),
        )
        monkeypatch.setattr(
            main_mod,
            "ingest_all",
            lambda _data_dir: (_ for _ in ()).throw(AssertionError("ingest_all should not run")),
        )

        main_mod._run_startup_ingest_if_needed()
