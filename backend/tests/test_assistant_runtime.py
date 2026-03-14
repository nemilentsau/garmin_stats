"""Tests for assistant runtime helpers."""

import asyncio

import app.services.assistant_runtime as runtime_mod
from app.models import ContextSnapshot
from app.services.assistant_runtime import _extract_delta, _extract_session_id


async def _collect(stream):
    events = []
    async for event in stream:
        events.append(event)
    return events


class _FakeStdout:
    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if self._lines:
            return self._lines.pop(0)
        return b""


class _FakeStderr:
    def __init__(self, data: bytes):
        self._data = data
        self.read_started = False

    async def read(self) -> bytes:
        self.read_started = True
        await asyncio.sleep(0)
        return self._data


class _FakeProcess:
    def __init__(self, *, stdout_lines: list[bytes], stderr_data: bytes = b"", returncode: int = 0):
        self.stdout = _FakeStdout(stdout_lines)
        self.stderr = _FakeStderr(stderr_data)
        self.returncode: int | None = None
        self._returncode = returncode

    async def wait(self) -> int:
        assert self.stderr.read_started
        await asyncio.sleep(0)
        self.returncode = self._returncode
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


class TestExtractDelta:
    def test_returns_text_for_stream_token_events(self):
        payload = {
            "type": "stream_event",
            "event": {
                "delta": {
                    "type": "text_delta",
                    "text": "sleep score improved",
                }
            },
        }

        assert _extract_delta(payload) == "sleep score improved"

    def test_ignores_non_text_events(self):
        payload = {"type": "stream_event", "event": {"delta": {"type": "tool_use"}}}

        assert _extract_delta(payload) == ""


class TestExtractSessionId:
    def test_reads_direct_session_id(self):
        assert _extract_session_id({"session_id": "session-1"}) == "session-1"

    def test_reads_nested_session_id(self):
        payload: dict[str, object] = {"result": {"session_id": "session-2"}}

        assert _extract_session_id(payload) == "session-2"


class TestClaudeCodeRuntime:
    def test_drains_stderr_concurrently_before_waiting(self, monkeypatch, tmp_path):
        runtime = runtime_mod.ClaudeCodeRuntime()
        fake_process = _FakeProcess(stdout_lines=[], stderr_data=b"verbose log")

        monkeypatch.setattr(runtime_mod, "_write_workspace_files", lambda *_args: tmp_path)

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        events = asyncio.run(
            _collect(
                runtime.stream_chat(
                    snapshot=ContextSnapshot(id="snapshot-1", snapshot_json={}),
                    user_message="How am I doing?",
                    model="sonnet",
                    session_id=None,
                )
            )
        )

        assert events[-1] == {"type": "done", "session_id": None}
