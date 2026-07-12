"""Async handlers that bridge durable jobs, workspaces, and Codex execution."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.prompts import (
    chat_prompt,
    distill_prompt,
    review_prompt,
)
from app.domains.coach.application.workspace import assemble_workspace
from app.domains.coach.contracts import (
    ChatOutput,
    CoachJob,
    DistillOutput,
    ReviewOutput,
)
from app.domains.coach.infra.runner import (
    CodexJobResult,
    ensure_thread_codex_home,
    run_codex_job,
)
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.coach.time import utc_now_iso

Runner = Callable[..., Awaitable[CodexJobResult]]


class CoachHandlers:
    def __init__(
        self,
        *,
        repo: SqliteCoachRepository,
        gateway: CoachReadGateway,
        workspace_root: Path,
        plot_cache_dir: Path,
        threads_dir: Path,
        logs_dir: Path,
        runner: Runner = run_codex_job,
        local_today=None,
    ) -> None:
        self.repo = repo
        self.gateway = gateway
        self.workspace_root = workspace_root
        self.plot_cache_dir = plot_cache_dir
        self.threads_dir = threads_dir
        self.logs_dir = logs_dir
        self.runner = runner
        self.local_today = local_today or (
            lambda: __import__("datetime").datetime.now().astimezone().date().isoformat()
        )

    async def execute(self, job: CoachJob) -> None:
        handlers = {
            "review_run": self._review,
            "review_skip": self._review,
            "chat_turn": self._chat,
            "distill_thread": self._distill,
        }
        handler = handlers.get(job.kind)
        if handler is None:
            self.fail_unexpected(job, ValueError(f"Unknown coach job kind: {job.kind}"))
            return
        await handler(job)

    async def _review(self, job: CoachJob) -> None:
        review_id = self._payload_text(job, "review_id")
        target_date = self._payload_text(job, "date")
        run_id = job.payload.get("run_id")
        current_run_id = run_id if isinstance(run_id, str) else None
        await asyncio.to_thread(
            self.repo.mark_review_generating, review_id, updated_at=utc_now_iso()
        )
        directory = self.workspace_root / "reviews" / review_id
        manifest = await asyncio.to_thread(
            assemble_workspace,
            self.gateway,
            self.repo,
            directory=directory,
            plot_cache_dir=self.plot_cache_dir,
            evidence_date=self.local_today(),
            target_date=target_date,
            question_md=review_prompt(job.kind),
            current_run_id=current_run_id,
            transcript=None,
        )
        result = await self.runner(
            kind=job.kind,
            job_id=job.id,
            attempt=job.attempt_count,
            prompt=review_prompt(job.kind),
            workspace=Path(manifest.directory),
            output_model=ReviewOutput,
            images=[Path(path) for path in manifest.current_images],
            codex_home=None,
            resume_session_id=None,
            logs_dir=self.logs_dir,
        )
        if not result.ok or not isinstance(result.output, ReviewOutput):
            await asyncio.to_thread(
                self.repo.fail_job,
                job.id,
                error=self._runner_error(result),
                finished_at=utc_now_iso(),
            )
            return
        await asyncio.to_thread(
            self.repo.complete_review_output,
            review_id=review_id,
            job_id=job.id,
            output=result.output,
            finished_at=utc_now_iso(),
        )

    async def _chat(self, job: CoachJob) -> None:
        thread_id = self._payload_text(job, "thread_id")
        thread = await asyncio.to_thread(self.repo.thread, thread_id)
        if thread is None:
            raise LookupError(f"Unknown coach thread: {thread_id}")
        transcript = await asyncio.to_thread(self.repo.messages_for, thread_id)
        resumed = thread.codex_session_id is not None
        directory = self.workspace_root / "threads" / thread_id
        manifest = await asyncio.to_thread(
            assemble_workspace,
            self.gateway,
            self.repo,
            directory=directory,
            plot_cache_dir=self.plot_cache_dir,
            evidence_date=self.local_today(),
            target_date=self.local_today(),
            question_md=chat_prompt(resumed=resumed),
            current_run_id=None,
            transcript=transcript,
        )
        home = ensure_thread_codex_home(self.threads_dir, thread_id)
        result = await self.runner(
            kind=job.kind,
            job_id=job.id,
            attempt=job.attempt_count,
            prompt=chat_prompt(resumed=resumed),
            workspace=Path(manifest.directory),
            output_model=ChatOutput,
            images=[],
            codex_home=home,
            resume_session_id=thread.codex_session_id,
            logs_dir=self.logs_dir,
        )
        if not result.ok or not isinstance(result.output, ChatOutput):
            await asyncio.to_thread(
                self.repo.fail_chat_output,
                job_id=job.id,
                thread_id=thread_id,
                error=self._runner_error(result),
                finished_at=utc_now_iso(),
            )
            return
        await asyncio.to_thread(
            self.repo.complete_chat_output,
            job_id=job.id,
            thread_id=thread_id,
            output=result.output,
            session_id=result.session_id,
            finished_at=utc_now_iso(),
        )

    async def _distill(self, job: CoachJob) -> None:
        thread_id = self._payload_text(job, "thread_id")
        transcript = await asyncio.to_thread(self.repo.messages_for, thread_id)
        directory = self.workspace_root / "threads" / thread_id
        manifest = await asyncio.to_thread(
            assemble_workspace,
            self.gateway,
            self.repo,
            directory=directory,
            plot_cache_dir=self.plot_cache_dir,
            evidence_date=self.local_today(),
            target_date=self.local_today(),
            question_md=distill_prompt(),
            current_run_id=None,
            transcript=transcript,
        )
        home = ensure_thread_codex_home(self.threads_dir, thread_id)
        result = await self.runner(
            kind=job.kind,
            job_id=job.id,
            attempt=job.attempt_count,
            prompt=distill_prompt(),
            workspace=Path(manifest.directory),
            output_model=DistillOutput,
            images=[],
            codex_home=home,
            resume_session_id=None,
            logs_dir=self.logs_dir,
        )
        if not result.ok or not isinstance(result.output, DistillOutput):
            await asyncio.to_thread(
                self.repo.fail_distill_output,
                job_id=job.id,
                thread_id=thread_id,
                error=self._runner_error(result),
                finished_at=utc_now_iso(),
            )
            return
        await asyncio.to_thread(
            self.repo.complete_distill_output,
            job_id=job.id,
            thread_id=thread_id,
            output=result.output,
            finished_at=utc_now_iso(),
        )
        await asyncio.to_thread(
            shutil.rmtree,
            self.threads_dir / thread_id / "codex-home",
            True,
        )

    def fail_unexpected(self, job: CoachJob, error: Exception) -> None:
        message = f"unexpected: {type(error).__name__}: {error}"
        if job.kind == "chat_turn":
            self.repo.fail_chat_output(
                job_id=job.id,
                thread_id=self._payload_text(job, "thread_id"),
                error=message,
                finished_at=utc_now_iso(),
            )
        elif job.kind == "distill_thread":
            self.repo.fail_distill_output(
                job_id=job.id,
                thread_id=self._payload_text(job, "thread_id"),
                error=message,
                finished_at=utc_now_iso(),
            )
        else:
            self.repo.fail_job(job.id, error=message, finished_at=utc_now_iso())

    @staticmethod
    def _payload_text(job: CoachJob, key: str) -> str:
        value = job.payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Coach job {job.id} lacks {key}")
        return value

    @staticmethod
    def _runner_error(result: CodexJobResult) -> str:
        return f"{result.error_kind or 'invalid_output'}: {result.error or 'no detail'}"
