"""Isolated Codex CLI process runner with strict structured-output validation."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.contracts.base import StrictDefaultsRequired
from app.domains.coach.contracts import (
    ChatOutput,
    DistillOutput,
    JobKind,
    ReviewOutput,
)

OutputModel = type[ReviewOutput] | type[ChatOutput] | type[DistillOutput]
OutputValue = ReviewOutput | ChatOutput | DistillOutput
ErrorKind = Literal[
    "timeout",
    "spawn",
    "exit",
    "missing_output",
    "invalid_output",
    "output_too_large",
]


class CodexJobResult(StrictDefaultsRequired):
    ok: bool
    session_id: str | None = None
    output: OutputValue | None = None
    usage: dict[str, int] | None = None
    error_kind: ErrorKind | None = None
    error: str | None = None


class _ExactOutputSchema:
    schema_mode: Literal["exact"] = "exact"

    def __call__(self, model: OutputModel) -> dict[str, object]:
        """Return the exact schema mode proven by the production contract probe."""
        return model.model_json_schema(mode="serialization")


output_schema = _ExactOutputSchema()


def _user_auth_path() -> Path:
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".codex/auth.json"


def _ensure_codex_home(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    auth_link = path / "auth.json"
    if auth_link.exists() or auth_link.is_symlink():
        if not auth_link.is_symlink() or auth_link.resolve() != _user_auth_path().resolve():
            raise ValueError(f"Codex home has unexpected auth entry: {auth_link}")
        return path
    source = _user_auth_path()
    if not source.is_file():
        raise FileNotFoundError(f"Codex auth is unavailable: {source}")
    auth_link.symlink_to(source)
    return path


def ensure_thread_codex_home(threads_dir: Path, thread_id: str) -> Path:
    """Create one persistent, config-free Codex home for a coach thread."""
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if not thread_id or any(character not in allowed for character in thread_id):
        raise ValueError(f"Unsafe thread id: {thread_id}")
    return _ensure_codex_home(threads_dir / thread_id / "codex-home/.codex")


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


def _events(path: Path) -> tuple[str | None, dict[str, int] | None]:
    session_id: str | None = None
    usage: dict[str, int] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        candidate = event.get("thread_id") or event.get("session_id")
        if session_id is None and isinstance(candidate, str):
            session_id = candidate
        raw_usage = event.get("usage")
        if isinstance(raw_usage, dict) and all(
            isinstance(key, str) and isinstance(value, int)
            for key, value in raw_usage.items()
        ):
            usage = dict(raw_usage)
    return session_id, usage


def _failure(kind: ErrorKind, error: str) -> CodexJobResult:
    return CodexJobResult(ok=False, error_kind=kind, error=error)


def _command(
    *,
    schema_path: Path,
    output_path: Path,
    workspace: Path,
    prompt: str,
    images: list[Path],
    resume_session_id: str | None,
) -> list[str]:
    command = ["codex", "exec"]
    if resume_session_id is not None:
        command.append("resume")
    command.extend(
        [
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "--skip-git-repo-check",
            "--model",
            os.environ.get("COACH_CODEX_MODEL", "gpt-5.6-sol"),
            "--output-schema",
            str(schema_path),
        ]
    )
    if resume_session_id is None:
        command.extend(["--sandbox", "read-only", "-C", str(workspace)])
        for image in images:
            command.extend(["-i", str(image)])
    command.extend(["-o", str(output_path)])
    if resume_session_id is not None:
        command.append(resume_session_id)
    command.append(prompt)
    return command


async def run_codex_job(
    *,
    kind: JobKind,
    job_id: str,
    attempt: int,
    prompt: str,
    workspace: Path,
    output_model: OutputModel,
    images: list[Path],
    codex_home: Path | None,
    resume_session_id: str | None,
    logs_dir: Path,
    timeout_s: float = 900,
) -> CodexJobResult:
    """Run one fresh attempt and accept only validated structured output."""
    del kind
    workspace.mkdir(parents=True, exist_ok=True)
    attempt_dir = workspace / "_runtime" / job_id / f"attempt-{attempt}"
    try:
        attempt_dir.mkdir(parents=True, exist_ok=False)
        active_home = _ensure_codex_home(
            codex_home or attempt_dir / "codex-home/.codex"
        )
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as error:
        return _failure("spawn", str(error))

    schema_path = attempt_dir / "schema.json"
    output_path = attempt_dir / "output.json"
    schema_path.write_text(
        json.dumps(output_schema(output_model), indent=2),
        encoding="utf-8",
    )
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{job_id}-attempt-{attempt}.stdout.jsonl"
    stderr_path = logs_dir / f"{job_id}-attempt-{attempt}.stderr.log"
    command = _command(
        schema_path=schema_path,
        output_path=output_path,
        workspace=workspace,
        prompt=prompt,
        images=images,
        resume_session_id=resume_session_id,
    )
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(active_home)
    process: asyncio.subprocess.Process | None = None
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=workspace,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
            except (FileNotFoundError, OSError) as error:
                return _failure("spawn", str(error))
            try:
                async with asyncio.timeout(timeout_s):
                    await process.wait()
            except TimeoutError:
                await _terminate_process_group(process)
                return _failure("timeout", f"Codex exceeded {timeout_s:g} seconds")
            except asyncio.CancelledError:
                await _terminate_process_group(process)
                raise
    finally:
        if process is not None and process.returncode is None:
            await _terminate_process_group(process)

    assert process is not None
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    if process.returncode != 0:
        return _failure(
            "exit",
            f"Codex exited {process.returncode}: {stderr_text.strip() or 'no stderr'}",
        )
    if not output_path.is_file():
        return _failure("missing_output", "Codex exited successfully without an output file")
    raw_output = output_path.read_text(encoding="utf-8", errors="replace")
    try:
        output = output_model.model_validate_json(raw_output)
    except ValidationError as error:
        error_kind: ErrorKind = (
            "output_too_large"
            if any(item["type"] == "string_too_long" for item in error.errors())
            else "invalid_output"
        )
        return _failure(error_kind, str(error))
    except ValueError as error:
        return _failure("invalid_output", str(error))
    session_id, usage = _events(stdout_path)
    return CodexJobResult(
        ok=True,
        session_id=session_id,
        output=output,
        usage=usage,
    )
