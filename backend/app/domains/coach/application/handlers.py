"""Async handlers that bridge durable jobs, workspaces, and Codex execution."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from pathlib import Path

from app.domains.coach.adapters import (
    MeasurementAssessmentValidationError,
    ReviewRevisionValidationError,
    SqliteCoachRepository,
)
from app.domains.coach.application.memory import CURRENT_MEMORY_POLICY_VERSION
from app.domains.coach.application.prompts import (
    BRIEF_BOOTSTRAP_INSTRUCTION,
    chat_prompt,
    distill_prompt,
    review_prompt,
    week_prompt,
)
from app.domains.coach.application.workspace import WorkspaceManifest, assemble_workspace
from app.domains.coach.contracts import (
    ArtifactRef,
    ChatOutput,
    CoachJob,
    DistillOutput,
    PlotObservation,
    ReviewOutput,
    WeekReviewOutput,
)
from app.domains.coach.infra.runner import (
    CodexJobResult,
    ensure_thread_codex_home,
    run_codex_job,
)
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.coach.time import local_today_iso, utc_now_iso

Runner = Callable[..., Awaitable[CodexJobResult]]


def _measurement_targets_from_payload(payload: dict[str, object]) -> list[tuple[str, str]]:
    """Read the day job's `measurement_targets` payload defensively.

    Task 9's shape is `list[dict[str, str]]`, but payload is untyped storage —
    tolerate malformed entries rather than raising, so one bad entry cannot
    take down an otherwise-valid day review job.
    """
    raw = payload.get("measurement_targets")
    targets: list[tuple[str, str]] = []
    if not isinstance(raw, list):
        return targets
    for entry in raw:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("run_id"), str)
            and isinstance(entry.get("occurrence_key"), str)
        ):
            targets.append((entry["run_id"], entry["occurrence_key"]))
    return targets


def _plot_evidence_errors(
    *,
    direct_refs: list[ArtifactRef],
    supporting_refs: list[ArtifactRef],
    observations: list[PlotObservation],
    manifest: WorkspaceManifest,
) -> list[str]:
    """Validate cited plot evidence against the exact assembled workspace."""
    current_plots = {Path(path).name for path in manifest.current_images}
    available_plots = current_plots | {
        ref.value for ref in manifest.resolved_refs if ref.kind == "plot"
    }
    output_plot_refs = {
        ref.value
        for ref in [*direct_refs, *supporting_refs]
        if ref.kind == "plot"
    }
    direct_plot_refs = {ref.value for ref in direct_refs if ref.kind == "plot"}
    observation_plots = {observation.plot for observation in observations}
    unknown_plots = sorted(
        (observation_plots - current_plots) | (output_plot_refs - available_plots)
    )
    unobserved_current_refs = sorted(
        (output_plot_refs & current_plots) - observation_plots
    )
    uncited_observations = sorted(observation_plots - direct_plot_refs)
    errors: list[str] = []
    if unknown_plots:
        errors.append("unavailable plot names: " + ", ".join(unknown_plots))
    if unobserved_current_refs:
        errors.append(
            "current plot refs without observations: "
            + ", ".join(unobserved_current_refs)
        )
    if uncited_observations:
        errors.append(
            "plot observations missing direct refs: "
            + ", ".join(uncited_observations)
        )
    return errors


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
        self.local_today = local_today or local_today_iso

    async def execute(self, job: CoachJob) -> None:
        handlers = {
            "review_run": self._review,
            "review_day": self._review,
            "review_week": self._week,
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
        occurrence_key = job.payload.get("occurrence_key")
        if job.kind == "review_day":
            today = await asyncio.to_thread(self.gateway.training_today, target_date)
            run_ids = sorted(
                {
                    card.associated_activity.run_id
                    for card in today.cards
                    if card.associated_activity is not None
                }
            )
            targets = _measurement_targets_from_payload(job.payload)
        else:
            run_ids = [current_run_id] if current_run_id else []
            targets = (
                [(current_run_id, occurrence_key)]
                if current_run_id and isinstance(occurrence_key, str)
                else []
            )
        prompt = review_prompt(job.kind, measurement_targets=targets)
        has_brief = (
            await asyncio.to_thread(
                self.repo.current_brief, policy_version=CURRENT_MEMORY_POLICY_VERSION
            )
        ) is not None
        if not has_brief:
            prompt = prompt + BRIEF_BOOTSTRAP_INSTRUCTION
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
            question_md=prompt,
            current_run_ids=run_ids,
            transcript=None,
        )
        result = await self.runner(
            kind=job.kind,
            job_id=job.id,
            attempt=job.attempt_count,
            prompt=prompt,
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
        supporting_refs = [
            *result.output.journal.refs,
            *[
                ref
                for historical_use in result.output.history_used
                for ref in historical_use.refs
            ],
        ]
        validation_errors = _plot_evidence_errors(
            direct_refs=result.output.refs,
            supporting_refs=supporting_refs,
            observations=result.output.plot_observations,
            manifest=manifest,
        )
        if validation_errors:
            await asyncio.to_thread(
                self.repo.fail_job,
                job.id,
                error=(
                    "invalid_output: inconsistent plot evidence: "
                    + "; ".join(validation_errors)
                ),
                finished_at=utc_now_iso(),
            )
            return
        try:
            await asyncio.to_thread(
                self.repo.complete_review_output,
                review_id=review_id,
                job_id=job.id,
                output=result.output,
                finished_at=utc_now_iso(),
                require_brief=not has_brief,
            )
        except MeasurementAssessmentValidationError as error:
            await asyncio.to_thread(
                self.repo.fail_job,
                job.id,
                error=f"invalid_output: {error}",
                finished_at=utc_now_iso(),
            )

    async def _week(self, job: CoachJob) -> None:
        review_id = self._payload_text(job, "review_id")
        week_start = self._payload_text(job, "week_start")
        week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
        recent = await asyncio.to_thread(
            self.gateway.recent_runs, evidence_date=week_end, limit=20
        )
        run_ids = sorted(
            {item.id for item in recent if week_start <= item.session_date <= week_end}
        )
        prompt = week_prompt()
        has_brief = (
            await asyncio.to_thread(
                self.repo.current_brief, policy_version=CURRENT_MEMORY_POLICY_VERSION
            )
        ) is not None
        if not has_brief:
            prompt = prompt + BRIEF_BOOTSTRAP_INSTRUCTION
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
            target_date=week_start,
            question_md=prompt,
            current_run_ids=run_ids,
            transcript=None,
        )
        result = await self.runner(
            kind=job.kind,
            job_id=job.id,
            attempt=job.attempt_count,
            prompt=prompt,
            workspace=Path(manifest.directory),
            output_model=WeekReviewOutput,
            images=[Path(path) for path in manifest.current_images],
            codex_home=None,
            resume_session_id=None,
            logs_dir=self.logs_dir,
        )
        if not result.ok or not isinstance(result.output, WeekReviewOutput):
            await asyncio.to_thread(
                self.repo.fail_job,
                job.id,
                error=self._runner_error(result),
                finished_at=utc_now_iso(),
            )
            return
        supporting_refs = [
            *result.output.journal.refs,
            *[
                ref
                for historical_use in result.output.history_used
                for ref in historical_use.refs
            ],
        ]
        validation_errors = _plot_evidence_errors(
            direct_refs=result.output.refs,
            supporting_refs=supporting_refs,
            observations=result.output.plot_observations,
            manifest=manifest,
        )
        if validation_errors:
            await asyncio.to_thread(
                self.repo.fail_job,
                job.id,
                error=(
                    "invalid_output: inconsistent plot evidence: "
                    + "; ".join(validation_errors)
                ),
                finished_at=utc_now_iso(),
            )
            return
        try:
            await asyncio.to_thread(
                self.repo.complete_week_review_output,
                review_id=review_id,
                job_id=job.id,
                output=result.output,
                finished_at=utc_now_iso(),
                require_brief=not has_brief,
            )
        except MeasurementAssessmentValidationError as error:
            await asyncio.to_thread(
                self.repo.fail_job,
                job.id,
                error=f"invalid_output: {error}",
                finished_at=utc_now_iso(),
            )

    async def _chat(self, job: CoachJob) -> None:
        thread_id = self._payload_text(job, "thread_id")
        thread = await asyncio.to_thread(self.repo.thread, thread_id)
        if thread is None:
            raise LookupError(f"Unknown coach thread: {thread_id}")
        transcript = await asyncio.to_thread(self.repo.messages_for, thread_id)
        resumed = thread.codex_session_id is not None
        linked_review = (
            None
            if thread.review_id is None
            else await asyncio.to_thread(self.repo.review, thread.review_id)
        )
        if thread.review_id is not None and linked_review is None:
            raise LookupError(f"Unknown linked coach review: {thread.review_id}")
        directory = self.workspace_root / "threads" / thread_id
        revision_requested = (
            job.payload.get("review_revision_requested") is True
        )
        prompt = chat_prompt(
            resumed=resumed,
            review_linked=linked_review is not None,
            revision_requested=revision_requested,
        )
        manifest = await asyncio.to_thread(
            assemble_workspace,
            self.gateway,
            self.repo,
            directory=directory,
            plot_cache_dir=self.plot_cache_dir,
            evidence_date=self.local_today(),
            target_date=(
                self.local_today()
                if linked_review is None
                else linked_review.date
            ),
            question_md=prompt,
            current_run_ids=(
                []
                if linked_review is None
                else ([linked_review.run_id] if linked_review.run_id else [])
            ),
            transcript=transcript,
            linked_review_id=thread.review_id,
        )
        home = ensure_thread_codex_home(self.threads_dir, thread_id)
        result = await self.runner(
            kind=job.kind,
            job_id=job.id,
            attempt=job.attempt_count,
            prompt=prompt,
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
        revision = result.output.review_revision
        if revision is not None:
            validation_errors = _plot_evidence_errors(
                direct_refs=revision.refs,
                supporting_refs=[
                    ref
                    for historical_use in revision.history_used
                    for ref in historical_use.refs
                ],
                observations=revision.plot_observations,
                manifest=manifest,
            )
            if validation_errors:
                await asyncio.to_thread(
                    self.repo.fail_chat_output,
                    job_id=job.id,
                    thread_id=thread_id,
                    error=(
                        "invalid_output: inconsistent plot evidence: "
                        + "; ".join(validation_errors)
                    ),
                    finished_at=utc_now_iso(),
                )
                return
        try:
            await asyncio.to_thread(
                self.repo.complete_chat_output,
                job_id=job.id,
                thread_id=thread_id,
                output=result.output,
                session_id=result.session_id,
                finished_at=utc_now_iso(),
            )
        except (
            MeasurementAssessmentValidationError,
            ReviewRevisionValidationError,
        ) as error:
            await asyncio.to_thread(
                self.repo.fail_chat_output,
                job_id=job.id,
                thread_id=thread_id,
                error=f"invalid_output: {error}",
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
            current_run_ids=[],
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
        thread_id = job.payload.get("thread_id")
        if job.kind == "chat_turn" and isinstance(thread_id, str):
            self.repo.fail_chat_output(
                job_id=job.id, thread_id=thread_id, error=message, finished_at=utc_now_iso()
            )
        elif job.kind == "distill_thread" and isinstance(thread_id, str):
            self.repo.fail_distill_output(
                job_id=job.id, thread_id=thread_id, error=message, finished_at=utc_now_iso()
            )
        else:
            # Malformed payload (missing/non-string thread_id): fall back to the
            # generic job failure so this last-resort path can never itself raise.
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
