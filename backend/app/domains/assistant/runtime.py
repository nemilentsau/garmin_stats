"""Claude Code runtime adapter for retrieval-first assistant chat.

The runtime owns subprocess execution and temporary workspace seeding for
deterministic evidence bundles. It deliberately receives all context from the
application layer instead of reading domain stores directly.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

from app.domains.assistant.application.types import AssistantEvidenceBundle, AssistantMemoryRecord

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_WORKSPACE_ROOT = _PROJECT_ROOT / "storage" / "assistant" / "workspaces"
_CLAUDE_CMD = os.environ.get("CLAUDE_CODE_CMD", "claude")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(nested) for key, nested in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def _write_workspace_files(
    *,
    evidence_bundle: AssistantEvidenceBundle,
    prior_messages: Sequence[object],
    memory_records: Sequence[AssistantMemoryRecord],
    prompt: str,
) -> Path:
    workspace = _WORKSPACE_ROOT / evidence_bundle.id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "evidence.json").write_text(
        json.dumps(_jsonable(evidence_bundle), indent=2),
        encoding="utf-8",
    )
    (workspace / "thread_messages.json").write_text(
        json.dumps([_jsonable(message) for message in prior_messages], indent=2),
        encoding="utf-8",
    )
    (workspace / "memory.json").write_text(
        json.dumps([_jsonable(record) for record in memory_records], indent=2),
        encoding="utf-8",
    )
    (workspace / "task.md").write_text(prompt, encoding="utf-8")
    return workspace


def _chat_prompt(user_message: str) -> str:
    return "\n".join([
        "You are a personal health and recovery assistant.",
        "Ground your answer using evidence.json, memory.json, and thread_messages.json.",
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
    """Run Claude Code in a workspace seeded with deterministic continuity files."""

    async def stream_chat(
        self,
        *,
        evidence_bundle: AssistantEvidenceBundle,
        prior_messages: Sequence[object],
        memory_records: Sequence[AssistantMemoryRecord],
        user_message: str,
        model: str,
    ) -> AsyncIterator[dict[str, str | None]]:
        prompt = _chat_prompt(user_message)
        workspace = await asyncio.to_thread(
            _write_workspace_files,
            evidence_bundle=evidence_bundle,
            prior_messages=prior_messages,
            memory_records=memory_records,
            prompt=prompt,
        )
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

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        captured_session_id: str | None = None
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
            yield {"type": "done", "session_id": captured_session_id}
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if stderr_task is not None and not stderr_task.done():
                stderr_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stderr_task
