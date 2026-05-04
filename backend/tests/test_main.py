"""Application-level middleware and exception handler tests."""

import asyncio
import json

from starlette.types import Message

import app.bootstrap.lifespan as lifespan_mod
import app.main as main_mod
from app.models import IngestResult, IngestStatus

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

        monkeypatch.setattr(
            lifespan_mod,
            "extract_existing_archives",
            fake_extract_existing_archives,
        )
        monkeypatch.setattr(lifespan_mod, "check_ingest_status", fake_check_ingest_status)
        monkeypatch.setattr(lifespan_mod, "ingest_all", fake_ingest_all)

        lifespan_mod._run_startup_ingest_if_needed()

        assert order == ["extract", "ingest"]

    def test_skips_ingest_when_disk_state_matches_database(self, monkeypatch):
        monkeypatch.setattr(lifespan_mod, "extract_existing_archives", lambda _data_dir: 0)
        monkeypatch.setattr(
            lifespan_mod,
            "check_ingest_status",
            lambda _data_dir: IngestStatus(
                needs_ingest=False,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=72,
                days_on_disk=72,
            ),
        )
        monkeypatch.setattr(
            lifespan_mod,
            "ingest_all",
            lambda _data_dir: (_ for _ in ()).throw(AssertionError("ingest_all should not run")),
        )

        lifespan_mod._run_startup_ingest_if_needed()

    def test_second_startup_run_is_a_no_op_after_initial_ingest(self, monkeypatch):
        order: list[str] = []
        statuses = iter(
            [
                IngestStatus(
                    needs_ingest=True,
                    last_ingest_time="2026-03-15T00:00:00Z",
                    days_in_db=0,
                    days_on_disk=72,
                ),
                IngestStatus(
                    needs_ingest=False,
                    last_ingest_time="2026-03-15T00:05:21Z",
                    days_in_db=72,
                    days_on_disk=72,
                ),
            ]
        )

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 0

        def fake_check_ingest_status(_data_dir):
            order.append("status")
            return next(statuses)

        def fake_ingest_all(_data_dir):
            order.append("ingest")
            return IngestResult(days_ingested=72, duration_ms=321)

        monkeypatch.setattr(
            lifespan_mod,
            "extract_existing_archives",
            fake_extract_existing_archives,
        )
        monkeypatch.setattr(lifespan_mod, "check_ingest_status", fake_check_ingest_status)
        monkeypatch.setattr(lifespan_mod, "ingest_all", fake_ingest_all)

        lifespan_mod._run_startup_ingest_if_needed()
        lifespan_mod._run_startup_ingest_if_needed()

        assert order == ["extract", "status", "ingest", "extract", "status"]


class TestExceptionHandlers:
    def test_lookup_error_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.domains.garmin_analytics.api.overview.load_dashboard_overview",
            lambda *_args: (_ for _ in ()).throw(LookupError("No dashboard data")),
        )

        status, _headers, body = asyncio.run(_asgi_request("/api/dashboard"))

        assert status == 404
        assert json.loads(body)["detail"] == "No dashboard data"

    def test_value_error_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.domains.routines.api.routines.get_schedule_window",
            lambda *_args, **_kwargs: (
                _ for _ in ()
            ).throw(ValueError("duration_days must be > 0")),
        )

        status, _headers, body = asyncio.run(
            _asgi_request("/api/routines/schedule-window?start_date=2026-03-02")
        )

        assert status == 400
        assert json.loads(body)["detail"] == "duration_days must be > 0"
