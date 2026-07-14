"""Outcome tests for coach job handlers and semantic memory persistence."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.handlers import CoachHandlers
from app.domains.coach.application.workspace import WorkspaceManifest
from app.domains.coach.contracts import (
    ArtifactRef,
    ChatOutput,
    CoachMeasurementAssessment,
    CoachThread,
    DistillOutput,
    ReviewOutput,
)
from app.domains.coach.infra.runner import CodexJobResult

NOW = "2026-07-12T12:00:00Z"


class FakeGateway:
    def run_detail(self, run_id: str):
        from tests.domains.coach.test_coach_context import _detail

        return _detail().model_copy(
            update={"session": _detail().session.model_copy(update={"id": run_id})}
        )


class FakeRunner:
    def __init__(self, results: list[CodexJobResult]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def __call__(self, **kwargs) -> CodexJobResult:
        self.calls.append(kwargs)
        return self.results.pop(0)


def _manifest(directory: Path, *, images: list[str] | None = None) -> WorkspaceManifest:
    directory.mkdir(parents=True, exist_ok=True)
    return WorkspaceManifest(
        directory=str(directory.resolve()),
        current_images=images or [],
    )


def _handlers(tmp_path, monkeypatch, repo, runner) -> CoachHandlers:
    calls = {"count": 0}

    def assemble(*args, directory: Path, **kwargs):
        del args, kwargs
        calls["count"] += 1
        return _manifest(directory)

    monkeypatch.setattr("app.domains.coach.application.handlers.assemble_workspace", assemble)
    monkeypatch.setattr(
        "app.domains.coach.application.handlers.ensure_thread_codex_home",
        lambda threads_dir, thread_id: threads_dir / thread_id / "codex-home/.codex",
    )
    handlers = CoachHandlers(
        repo=repo,
        gateway=FakeGateway(),  # type: ignore[arg-type]
        workspace_root=tmp_path / "workspaces",
        plot_cache_dir=tmp_path / "plots",
        threads_dir=tmp_path / "threads",
        logs_dir=tmp_path / "logs",
        runner=runner,
        local_today=lambda: "2026-07-12",
    )
    handlers.workspace_call_counter = calls  # type: ignore[attr-defined]
    return handlers


def _review_output() -> ReviewOutput:
    return ReviewOutput(
        verdict="compliant",
        review_md="The session met the intended easy-day purpose.",
        observations=["Effort stayed controlled."],
        concerns=[],
        suggestions=[],
        plan_adjustments=[],
        evidence_limits=[],
        plots_viewed=["current-1.png"],
        refs=[ArtifactRef(kind="run", value="run-1")],
        journal_entry_md="Easy-day execution was controlled; compare recovery tomorrow.",
        brief_md="Current approach: protect easy days and compare next-day recovery.",
    )


def test_review_success_persists_review_memory_and_full_brief_atomically(
    tmp_path, monkeypatch
):
    repo = SqliteCoachRepository()
    review, _, _ = repo.enqueue_run_review(
        run_id="run-1", date="2026-07-11", occurrence_key="run-am"
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    runner = FakeRunner([CodexJobResult(ok=True, output=_review_output())])
    handlers = _handlers(tmp_path, monkeypatch, repo, runner)

    asyncio.run(handlers.execute(job))

    saved = repo.review(review.id)
    assert saved is not None
    assert saved.status == "complete"
    assert saved.verdict == "compliant"
    assert saved.refs == [ArtifactRef(kind="run", value="run-1")]
    assert repo.job(job.id).status == "complete"  # type: ignore[union-attr]
    assert repo.list_journal()[0].content_md.startswith("Easy-day execution")
    assert repo.current_brief().content_md.startswith("Current approach")  # type: ignore[union-attr]


def test_review_failure_changes_no_memory_and_supports_same_job_retry(tmp_path, monkeypatch):
    repo = SqliteCoachRepository()
    review, queued, _ = repo.enqueue_run_review(
        run_id="run-1", date="2026-07-11", occurrence_key=None
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    runner = FakeRunner([CodexJobResult(ok=False, error_kind="invalid_output", error="bad")])
    handlers = _handlers(tmp_path, monkeypatch, repo, runner)

    asyncio.run(handlers.execute(job))

    assert repo.list_journal() == []
    assert repo.current_brief() is None
    assert repo.review(review.id).status == "failed"  # type: ignore[union-attr]
    retried = repo.retry_failed_job(queued.id, available_at=NOW)
    assert retried.id == queued.id


def test_review_target_mismatch_fails_job_without_persisting_assessment(
    tmp_path, monkeypatch
):
    repo = SqliteCoachRepository()
    review, _, _ = repo.enqueue_run_review(
        run_id="run-1", date="2026-07-11", occurrence_key="running:lthr:d08"
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    output = _review_output().model_copy(
        update={
            "measurement_assessment": CoachMeasurementAssessment(
                run_id="run-1",
                occurrence_key="running:lthr:d15",
                status="valid",
                rationale="Credible effort.",
            )
        }
    )
    handlers = _handlers(
        tmp_path,
        monkeypatch,
        repo,
        FakeRunner([CodexJobResult(ok=True, output=output)]),
    )

    asyncio.run(handlers.execute(job))

    saved = repo.review(review.id)
    assert saved is not None
    assert saved.status == "failed"
    assert saved.measurement_assessment is None
    assert repo.job(job.id).status == "failed"  # type: ignore[union-attr]
    assert repo.list_journal() == []


def test_chat_refreshes_each_turn_uses_resume_marker_and_persists_refs(tmp_path, monkeypatch):
    repo = SqliteCoachRepository()
    repo.insert_thread(
        CoachThread(
            id="thread-1",
            title="Training",
            status="open",
            codex_session_id="session-old",
            created_at=NOW,
            last_activity_at=NOW,
        )
    )
    repo.enqueue_chat_message(thread_id="thread-1", content_md="What next?")
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    output = ChatOutput(
        answer_md="Keep tomorrow easy.",
        evidence_limits=[],
        refs=[ArtifactRef(kind="date", value="2026-07-12")],
    )
    runner = FakeRunner([CodexJobResult(ok=True, session_id="session-new", output=output)])
    handlers = _handlers(tmp_path, monkeypatch, repo, runner)

    asyncio.run(handlers.execute(job))

    messages = repo.messages_for("thread-1")
    assert [message.role for message in messages] == ["user", "coach"]
    assert messages[-1].refs == output.refs
    assert repo.thread("thread-1").codex_session_id == "session-new"  # type: ignore[union-attr]
    assert "Workspace files were refreshed" in str(runner.calls[0]["prompt"])
    assert handlers.workspace_call_counter["count"] == 1  # type: ignore[attr-defined]


def test_chat_failure_appends_availability_system_message(tmp_path, monkeypatch):
    repo = SqliteCoachRepository()
    repo.insert_thread(
        CoachThread(
            id="thread-1",
            title="Training",
            status="open",
            created_at=NOW,
            last_activity_at=NOW,
        )
    )
    repo.enqueue_chat_message(thread_id="thread-1", content_md="Question")
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    handlers = _handlers(
        tmp_path,
        monkeypatch,
        repo,
        FakeRunner([CodexJobResult(ok=False, error_kind="timeout", error="late")]),
    )

    asyncio.run(handlers.execute(job))

    messages = repo.messages_for("thread-1")
    assert messages[-1].role == "system"
    assert "unavailable" in messages[-1].content_md.lower()
    assert repo.job(job.id).status == "failed"  # type: ignore[union-attr]


def test_chat_invalid_assessment_context_fails_without_persisting_assessment(
    tmp_path, monkeypatch
):
    repo = SqliteCoachRepository()
    repo.insert_thread(
        CoachThread(
            id="thread-1",
            title="Training",
            status="open",
            created_at=NOW,
            last_activity_at=NOW,
        )
    )
    repo.enqueue_chat_message(thread_id="thread-1", content_md="Assess the test")
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    output = ChatOutput(
        answer_md="Assessment",
        evidence_limits=[],
        refs=[],
        measurement_assessment=CoachMeasurementAssessment(
            run_id="run-1",
            occurrence_key="running:lthr:d08",
            status="valid",
            rationale="Credible effort.",
        ),
    )
    handlers = _handlers(
        tmp_path,
        monkeypatch,
        repo,
        FakeRunner([CodexJobResult(ok=True, output=output)]),
    )

    asyncio.run(handlers.execute(job))

    messages = repo.messages_for("thread-1")
    assert [message.role for message in messages] == ["user", "system"]
    assert all(message.measurement_assessment is None for message in messages)
    assert repo.job(job.id).status == "failed"  # type: ignore[union-attr]


def test_distill_success_closes_thread_persists_memory_then_deletes_home(
    tmp_path, monkeypatch
):
    repo = SqliteCoachRepository()
    repo.insert_thread(
        CoachThread(
            id="thread-1",
            title="Training",
            status="closing",
            created_at=NOW,
            last_activity_at=NOW,
        )
    )
    home = tmp_path / "threads/thread-1/codex-home/.codex"
    home.mkdir(parents=True)
    job = repo.enqueue_distill(thread_id="thread-1")
    claimed = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None and claimed.id == job.id
    output = DistillOutput(
        journal_entry_md="The thread decided to keep the next run easy.",
        refs=[ArtifactRef(kind="date", value="2026-07-12")],
    )
    handlers = _handlers(
        tmp_path, monkeypatch, repo, FakeRunner([CodexJobResult(ok=True, output=output)])
    )

    asyncio.run(handlers.execute(claimed))

    assert repo.thread("thread-1").status == "closed"  # type: ignore[union-attr]
    assert repo.list_journal()[0].content_md.startswith("The thread decided")
    assert not home.exists()


def test_distill_failure_keeps_home_and_marks_close_failed(tmp_path, monkeypatch):
    repo = SqliteCoachRepository()
    repo.insert_thread(
        CoachThread(
            id="thread-1",
            title="Training",
            status="closing",
            created_at=NOW,
            last_activity_at=NOW,
        )
    )
    home = tmp_path / "threads/thread-1/codex-home/.codex"
    home.mkdir(parents=True)
    claimed = repo.enqueue_distill(thread_id="thread-1")
    claimed = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None
    handlers = _handlers(
        tmp_path,
        monkeypatch,
        repo,
        FakeRunner([CodexJobResult(ok=False, error_kind="exit", error="bad")]),
    )

    asyncio.run(handlers.execute(claimed))

    assert repo.thread("thread-1").status == "close_failed"  # type: ignore[union-attr]
    assert home.is_dir()
