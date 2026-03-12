"""Claude Code runtime wrapper."""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from ..models import ContextSnapshot

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_WORKSPACE_ROOT = _PROJECT_ROOT / "storage" / "assistant" / "workspaces"
_CLAUDE_CMD = os.environ.get("CLAUDE_CODE_CMD", "claude")


def _write_workspace_files(snapshot: ContextSnapshot, prompt: str) -> Path:
    workspace = _WORKSPACE_ROOT / snapshot.id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "context.json").write_text(
        json.dumps(snapshot.snapshot_json, indent=2),
        encoding="utf-8",
    )
    (workspace / "context.md").write_text(snapshot.summary_markdown or "", encoding="utf-8")
    (workspace / "task.md").write_text(prompt, encoding="utf-8")
    return workspace


def _chat_prompt(user_message: str) -> str:
    return "\n".join([
        "You are a personal health and recovery assistant.",
        "Read context.md first, then answer the user using actual numbers when available.",
        "Be explicit about uncertainty and confounders.",
        "Do not diagnose medical conditions.",
        "Use concise markdown.",
        "",
        f"User message: {user_message}",
    ])


def _extract_delta(payload: dict[str, object]) -> str:
    if payload.get("type") != "stream_event":
        return ""
    event = payload.get("event")
    if not isinstance(event, dict):
        return ""
    delta = event.get("delta")
    if not isinstance(delta, dict):
        return ""
    if delta.get("type") != "text_delta":
        return ""
    text = delta.get("text")
    return text if isinstance(text, str) else ""


def _extract_session_id(payload: dict[str, object]) -> str | None:
    direct = payload.get("session_id")
    if isinstance(direct, str):
        return direct
    result = payload.get("result")
    if isinstance(result, dict):
        nested = result.get("session_id")
        if isinstance(nested, str):
            return nested
    event = payload.get("event")
    if isinstance(event, dict):
        nested = event.get("session_id")
        if isinstance(nested, str):
            return nested
    return None


class ClaudeCodeRuntime:
    """Run Claude Code in a constrained workspace for assistant prompts."""

    async def stream_chat(
        self,
        *,
        snapshot: ContextSnapshot,
        user_message: str,
        model: str,
        session_id: str | None,
    ) -> AsyncIterator[dict[str, str]]:
        prompt = _chat_prompt(user_message)
        workspace = _write_workspace_files(snapshot, prompt)
        cmd = [
            _CLAUDE_CMD,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--allowedTools",
            "Read",
            "--model",
            model,
        ]
        if session_id:
            cmd.extend(["--resume", session_id])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        captured_session_id = session_id
        stderr_task: asyncio.Task[bytes] | None = None
        try:
            assert process.stdout is not None
            if process.stderr is not None:
                stderr_task = asyncio.create_task(process.stderr.read())
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                raw = line.decode("utf-8").strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if captured_session_id is None:
                    captured_session_id = _extract_session_id(payload)
                delta = _extract_delta(payload)
                if delta:
                    yield {"type": "delta", "text": delta}

            returncode = await process.wait()
            stderr = ""
            if stderr_task is not None:
                stderr = (await stderr_task).decode("utf-8").strip()
            if returncode != 0:
                raise RuntimeError(stderr or f"Claude exited with status {returncode}")
            yield {
                "type": "done",
                "session_id": captured_session_id or f"session-{uuid4().hex}",
            }
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if stderr_task is not None and not stderr_task.done():
                stderr_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stderr_task
