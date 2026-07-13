"""Process-boundary tests for isolated, validated Codex execution."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from app.domains.coach.contracts import (
    ArtifactRef,
    ChatOutput,
    DistillOutput,
    JobKind,
    ReviewOutput,
)
from app.domains.coach.infra.runner import (
    ensure_thread_codex_home,
    output_schema,
    run_codex_job,
)


def _review_json(**updates) -> str:
    value = ReviewOutput(
        verdict="compliant",
        review_md="Sound run.",
        observations=[],
        concerns=[],
        suggestions=[],
        plan_adjustments=[],
        evidence_limits=[],
        plots_viewed=[],
        refs=[ArtifactRef(kind="run", value="run-1")],
        journal_entry_md="Repeat the same comparison next week.",
    ).model_dump()
    value.update(updates)
    return json.dumps(value)


def _chat_json() -> str:
    return ChatOutput(answer_md="Take an easy day.", evidence_limits=[], refs=[]).model_dump_json()


async def _run(
    tmp_path: Path,
    *,
    kind: JobKind = "review_run",
    output_model: type[ReviewOutput] | type[ChatOutput] | type[DistillOutput] = ReviewOutput,
    codex_home: Path | None = None,
    resume_session_id: str | None = None,
    images: list[Path] | None = None,
    attempt: int = 1,
):
    return await run_codex_job(
        kind=kind,  # type: ignore[arg-type]
        job_id="job-1",
        attempt=attempt,
        prompt="Read question.md and answer.",
        workspace=tmp_path / "workspace",
        output_model=output_model,
        images=images or [],
        codex_home=codex_home,
        resume_session_id=resume_session_id,
        logs_dir=tmp_path / "logs",
        timeout_s=0.4,
    )


def test_review_command_is_ephemeral_isolated_and_attaches_images(
    tmp_path, codex_stub, monkeypatch
):
    image = tmp_path / "workspace/current/run.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    monkeypatch.setenv("CODEX_STUB_OUTPUT", _review_json())

    result = asyncio.run(_run(tmp_path, images=[image]))
    record = json.loads(codex_stub.read_text())
    argv = record["argv"]

    assert result.ok is True
    assert isinstance(result.output, ReviewOutput)
    assert result.session_id == "session-123"
    assert result.usage == {"input_tokens": 11, "output_tokens": 7}
    for flag in ("--ignore-user-config", "--ignore-rules", "--json", "--skip-git-repo-check"):
        assert flag in argv
    assert "--ephemeral" in argv
    assert argv[argv.index("--config") + 1] == "project_doc_max_bytes=0"
    assert argv[:1] == ["exec"]
    staged_image = Path(argv[argv.index("-i") + 1])
    assert staged_image == Path(record["cwd"]) / "current/run.png"
    assert record["cwd"] != str(tmp_path / "workspace")
    assert not Path(record["cwd"]).exists()
    assert record["home"] == str(Path(record["codex_home"]).parent)
    assert record["codex_home"].endswith("_runtime/job-1/attempt-1/codex-home/.codex")


def test_cli_schema_generation_is_exact_recorded_mode():
    assert output_schema(ReviewOutput) == ReviewOutput.model_json_schema(mode="serialization")
    assert output_schema.schema_mode == "exact"  # type: ignore[attr-defined]


def test_chat_home_first_turn_and_resume_command(tmp_path, codex_stub, monkeypatch):
    monkeypatch.setenv("CODEX_STUB_OUTPUT", _chat_json())
    home = ensure_thread_codex_home(tmp_path / "threads", "thread-1")

    first = asyncio.run(
        _run(tmp_path, kind="chat_turn", output_model=ChatOutput, codex_home=home)
    )
    first_argv = json.loads(codex_stub.read_text())["argv"]
    resumed = asyncio.run(
        _run(
            tmp_path,
            kind="chat_turn",
            output_model=ChatOutput,
            codex_home=home,
            resume_session_id="session-old",
            attempt=2,
        )
    )
    second = json.loads(codex_stub.read_text())

    assert first.ok and resumed.ok
    assert "resume" not in first_argv
    assert "--ephemeral" not in first_argv
    assert second["argv"][:2] == ["exec", "resume"]
    assert "session-old" in second["argv"]
    assert "--ephemeral" not in second["argv"]
    assert second["home"] == str(home.parent)
    assert second["codex_home"] == str(home)


@pytest.mark.parametrize(
    ("behavior", "output", "error_kind"),
    [
        ("nonzero", _review_json(), "exit"),
        ("missing", _review_json(), "missing_output"),
        ("malformed", _review_json(), "invalid_output"),
        ("success", '{"verdict":"compliant"}', "invalid_output"),
    ],
)
def test_exit_missing_malformed_and_schema_invalid_are_distinct(
    tmp_path, codex_stub, monkeypatch, behavior, output, error_kind
):
    del codex_stub
    monkeypatch.setenv("CODEX_STUB_BEHAVIOR", behavior)
    monkeypatch.setenv("CODEX_STUB_OUTPUT", output)

    result = asyncio.run(_run(tmp_path))

    assert result.ok is False
    assert result.error_kind == error_kind
    if behavior == "nonzero":
        assert "stub exploded" in (result.error or "")


def test_overlength_output_is_not_truncated(tmp_path, codex_stub, monkeypatch):
    del codex_stub
    raw = _review_json(journal_entry_md="x" * 1601)
    monkeypatch.setenv("CODEX_STUB_OUTPUT", raw)

    result = asyncio.run(_run(tmp_path))

    assert result.error_kind == "output_too_large"
    output_path = tmp_path / "workspace/_runtime/job-1/attempt-1/output.json"
    assert json.loads(output_path.read_text())["journal_entry_md"] == "x" * 1601


def test_stale_output_cannot_be_read_by_new_attempt(tmp_path, codex_stub, monkeypatch):
    del codex_stub
    old = tmp_path / "workspace/_runtime/job-1/attempt-1/output.json"
    old.parent.mkdir(parents=True)
    old.write_text(_review_json())
    monkeypatch.setenv("CODEX_STUB_BEHAVIOR", "missing")

    result = asyncio.run(_run(tmp_path, attempt=2))

    assert result.error_kind == "missing_output"


def test_timeout_terminates_process_group_and_writes_logs(
    tmp_path, codex_stub, monkeypatch
):
    del codex_stub
    child_pid = tmp_path / "child.pid"
    monkeypatch.setenv("CODEX_STUB_BEHAVIOR", "sleep")
    monkeypatch.setenv("CODEX_STUB_CHILD_PID", str(child_pid))

    result = asyncio.run(_run(tmp_path))

    assert result.error_kind == "timeout"
    assert (tmp_path / "logs/job-1-attempt-1.stderr.log").is_file()
    pid = int(child_pid.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_cancellation_terminates_process_group_and_reraises(
    tmp_path, codex_stub, monkeypatch
):
    del codex_stub
    child_pid = tmp_path / "child.pid"
    monkeypatch.setenv("CODEX_STUB_BEHAVIOR", "sleep")
    monkeypatch.setenv("CODEX_STUB_CHILD_PID", str(child_pid))
    async def exercise() -> None:
        task = asyncio.create_task(_run(tmp_path))
        for _ in range(50):
            if child_pid.exists():
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    pid = int(child_pid.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_missing_binary_is_spawn_failure(tmp_path, codex_stub, monkeypatch):
    del codex_stub
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    result = asyncio.run(_run(tmp_path))

    assert result.error_kind == "spawn"


def test_thread_home_creation_is_idempotent_and_symlinks_only_auth(tmp_path, monkeypatch):
    home = tmp_path / "home"
    auth = home / ".codex/auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text("auth")
    (home / ".codex/config.toml").write_text("dangerous=true")
    monkeypatch.setenv("HOME", str(home))

    first = ensure_thread_codex_home(tmp_path / "threads", "thread-1")
    second = ensure_thread_codex_home(tmp_path / "threads", "thread-1")

    assert first == second
    assert (first / "auth.json").is_symlink()
    assert not (first / "config.toml").exists()
    assert [path.name for path in first.iterdir()] == ["auth.json"]


def test_explicit_source_codex_home_supplies_authentication(tmp_path, monkeypatch):
    source = tmp_path / "source-codex"
    auth = source / "auth.json"
    source.mkdir()
    auth.write_text("auth")
    monkeypatch.setenv("HOME", str(tmp_path / "ordinary-home"))
    monkeypatch.setenv("CODEX_HOME", str(source))

    isolated = ensure_thread_codex_home(tmp_path / "threads", "thread-1")

    assert (isolated / "auth.json").resolve() == auth.resolve()
