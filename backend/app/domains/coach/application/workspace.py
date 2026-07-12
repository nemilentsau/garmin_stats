"""Assemble bounded, hierarchical evidence workspaces for coach model calls."""

from __future__ import annotations

import re
import shutil
from datetime import date, timedelta
from pathlib import Path

from app.contracts.base import StrictDefaultsRequired
from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.contracts import ArtifactRef, CoachMessage, JournalEntry
from app.domains.coach.domain.context import (
    HistoricalRunContext,
    capabilities_markdown,
    compare_whole_session,
    digest_markdown,
    laps_markdown,
    run_summary_markdown,
)
from app.domains.coach.infra.plots import (
    render_current_run_stack,
    render_library_panel,
)
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.garmin_analytics.contracts import DashboardOverviewResponse, RunListItem
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.training.contracts import TrainingTodayCard

_SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")


class WorkspaceManifest(StrictDefaultsRequired):
    directory: str
    current_images: list[str] = []
    historical_run_ids: list[str] = []
    resolved_refs: list[ArtifactRef] = []


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe(value: str) -> str:
    if not value or _SAFE_ID.fullmatch(value) is None or value in {".", ".."}:
        raise ValueError(f"Unsafe artifact reference: {value}")
    return value


def _first_sentence(text: str) -> str:
    stripped = " ".join(text.split())
    stop = stripped.find(".")
    return stripped if stop < 0 else stripped[: stop + 1]


def _training_card_for_run(
    gateway: CoachReadGateway, run: RunListItem
) -> TrainingTodayCard | None:
    for card in gateway.training_today(run.session_date).cards:
        activity = card.associated_activity
        if activity is not None and activity.run_id == run.id:
            return card
    return None


def _run_context(
    gateway: CoachReadGateway,
    run: RunListItem,
    metric_by_date: dict[str, DailyMetric],
) -> HistoricalRunContext:
    detail = gateway.run_detail(run.id)
    card = _training_card_for_run(gateway, run)
    return HistoricalRunContext(
        run=run,
        detail=detail,
        training_card=card,
        morning_metric=metric_by_date.get(run.session_date),
        comparison=compare_whole_session(detail=detail, training_card=card),
    )


def _export_run(
    gateway: CoachReadGateway,
    *,
    run: RunListItem,
    destination: Path,
    plot_cache_dir: Path,
    metric_by_date: dict[str, DailyMetric],
) -> HistoricalRunContext:
    context = _run_context(gateway, run, metric_by_date)
    series = gateway.run_series(run.id)
    panel = render_library_panel(plot_cache_dir, context.detail, series)
    _write(destination / "summary.md", run_summary_markdown(context))
    _write(destination / "laps.md", laps_markdown(context))
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(panel, destination / "plot.png")
    return context


def _journal_markdown(entry: JournalEntry) -> str:
    refs = "\n".join(f"- {ref.kind}: {ref.value}" for ref in entry.refs) or "- none"
    return (
        f"# Journal entry {entry.id}\n\n"
        f"- Timestamp: {entry.ts}\n- Kind: {entry.kind}\n- Source: {entry.source_id}\n\n"
        f"{entry.content_md}\n\n## References\n\n{refs}\n"
    )


def _export_journal(
    directory: Path, entries: list[JournalEntry], *, recent_limit: int
) -> None:
    archive = directory / "journal/archive"
    for entry in entries:
        _write(archive / f"{_safe(entry.id)}.md", _journal_markdown(entry))
    recent = entries[-recent_limit:]
    older = entries[: -recent_limit] if len(entries) > recent_limit else []
    recent_text = "# Recent coach journal\n\n" + (
        "\n\n---\n\n".join(_journal_markdown(entry) for entry in recent)
        if recent
        else "No coach journal entries yet."
    )
    index_lines = ["# Older coach journal index", ""]
    if older:
        index_lines.extend(
            f"- {entry.ts} | {entry.kind} | {entry.id} | {_first_sentence(entry.content_md)}"
            for entry in older
        )
    else:
        index_lines.append("No older coach journal entries.")
    _write(directory / "journal/recent.md", recent_text + "\n")
    _write(directory / "journal/index.md", "\n".join(index_lines) + "\n")


def _plan_markdown(gateway: CoachReadGateway, target_date: str) -> str:
    target = date.fromisoformat(target_date)
    start = (target - timedelta(days=3)).isoformat()
    window = gateway.training_window(start, 7)
    today = gateway.training_today(target_date)
    status = gateway.block_status()
    lines = ["# Training plan evidence", "", f"Target occurrence date: {target_date}", ""]
    if status is None:
        lines.extend(["No active training block.", ""])
    else:
        block = status.block
        target_day = (target - date.fromisoformat(block.window.start)).days + 1
        lines.extend(
            [
                f"- Block: {block.id}",
                f"- Identity: {block.identity}",
                f"- Target block day: {target_day}",
                f"- Block window: {block.window.start} for {block.window.days} days",
                "",
                "## Exit criteria",
                "",
                block.model_dump_json(indent=2, include={"exit_criteria"}),
                "",
                "## Declared review specs",
                "",
                block.model_dump_json(indent=2, include={"review_specs"}),
                "",
                (
                    "Declared estimator outputs are unavailable unless an existing "
                    "computed response explicitly supplies them."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Seven-day schedule around target",
            "",
            window.model_dump_json(indent=2),
            "",
            "## Full target prescription and captured state",
            "",
            today.model_dump_json(indent=2),
            "",
        ]
    )
    return "\n".join(lines)


def _recovery_markdown(overview: DashboardOverviewResponse | None) -> str:
    if overview is None:
        return "# Recovery evidence\n\nNo recovery overview available.\n"
    lines = [
        "# Recovery evidence",
        "",
        f"- Date: {overview.date}",
        f"- State: {overview.state.band or 'unknown'} / {overview.state.trend or 'unknown'}",
        f"- Score z: {overview.state.score_z if overview.state.score_z is not None else 'unknown'}",
        (
            f"- Meaningful change: {overview.change.is_meaningful}; "
            f"direction={overview.change.direction or 'unknown'}; "
            "delta7_z="
            + (
                str(overview.change.delta7_z)
                if overview.change.delta7_z is not None
                else "unknown"
            )
        ),
        "",
        "## Evidence rows",
        "",
    ]
    if overview.evidence:
        lines.extend(
            (
                f"- {row.label}: "
                f"{row.latest_value if row.latest_value is not None else 'unknown'} "
                f"{row.unit}; "
                f"baseline={row.baseline if row.baseline is not None else 'unknown'}; "
                f"delta_z={row.delta_z if row.delta_z is not None else 'unknown'}; "
                f"coverage_ok={row.coverage_ok}; degraded={row.degraded}"
            )
            for row in overview.evidence
        )
    else:
        lines.append("- No recovery evidence rows available.")
    lines.extend(
        [
            "",
            "## Health flags",
            "",
            f"- Oxygen: {overview.flags.oxygen.status}",
            f"- Thermoregulation: {overview.flags.thermoregulation.status}",
            "",
        ]
    )
    return "\n".join(lines)


def _transcript_markdown(messages: list[CoachMessage]) -> str:
    lines = ["# Conversation transcript", ""]
    for message in messages:
        lines.extend(
            [
                f"## {message.role} · {message.created_at} · {message.id}",
                "",
                message.content_md,
                "",
            ]
        )
        if message.refs:
            lines.extend(["References:", *[f"- {r.kind}: {r.value}" for r in message.refs], ""])
    return "\n".join(lines)


def _refs(entries: list[JournalEntry], transcript: list[CoachMessage] | None) -> list[ArtifactRef]:
    candidates = [ref for entry in entries for ref in entry.refs]
    if transcript is not None:
        candidates.extend(ref for message in transcript for ref in message.refs)
    unique: dict[tuple[str, str], ArtifactRef] = {}
    for ref in candidates:
        unique[(ref.kind, ref.value)] = ref
    return [unique[key] for key in sorted(unique)]


def _write_date_ref(gateway: CoachReadGateway, destination: Path, value: str) -> None:
    target = date.fromisoformat(value).isoformat()
    metrics = [item for item in gateway.daily_metrics() if item.date == target]
    checkins = [item for item in gateway.checkins() if item.date == target]
    notes = [item for item in gateway.notes() if item.date == target]
    content = "\n".join(
        [
            f"# Date context {target}",
            "",
            "## Training",
            gateway.training_today(target).model_dump_json(indent=2),
            "",
            "## Daily metrics",
            *(item.model_dump_json(indent=2) for item in metrics),
            *( ["No daily metric available."] if not metrics else [] ),
            "",
            "## Check-ins",
            *(item.model_dump_json(indent=2) for item in checkins),
            *( ["No check-in available."] if not checkins else [] ),
            "",
            "## Notes",
            *(item.model_dump_json(indent=2) for item in notes),
            *( ["No note available."] if not notes else [] ),
            "",
        ]
    )
    _write(destination, content)


def assemble_workspace(
    gateway: CoachReadGateway,
    repo: SqliteCoachRepository,
    *,
    directory: Path,
    plot_cache_dir: Path,
    evidence_date: str,
    target_date: str,
    question_md: str,
    current_run_id: str | None,
    transcript: list[CoachMessage] | None,
    historical_run_limit: int = 20,
    recent_journal_limit: int = 10,
) -> WorkspaceManifest:
    """Refresh model-readable evidence while retaining attempt diagnostics."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("journal", "runs", "current", "refs"):
        path = directory / name
        if path.exists():
            shutil.rmtree(path)

    _write(directory / "evidence-capabilities.md", capabilities_markdown())
    brief = repo.current_brief()
    _write(
        directory / "brief.md",
        (
            brief.content_md + "\n"
            if brief is not None
            else "No durable coach brief yet; this is a first-use context.\n"
        ),
    )
    journal = repo.list_journal()
    _export_journal(directory, journal, recent_limit=recent_journal_limit)
    _write(directory / "plan.md", _plan_markdown(gateway, target_date))
    _write(directory / "recovery.md", _recovery_markdown(gateway.recovery_overview()))

    metrics = gateway.daily_metrics()
    metric_by_date = {metric.date: metric for metric in metrics}
    recent_runs = gateway.recent_runs(evidence_date=evidence_date, limit=historical_run_limit)
    contexts: list[HistoricalRunContext] = []
    for run in reversed(recent_runs):
        contexts.append(
            _export_run(
                gateway,
                run=run,
                destination=directory / "runs" / _safe(run.id),
                plot_cache_dir=plot_cache_dir,
                metric_by_date=metric_by_date,
            )
        )
    digest = (
        digest_markdown(contexts)
        if contexts
        else "# Recent run digest\n\nNo runs available.\n"
    )
    _write(directory / "runs/digest.md", digest)

    current_images: list[str] = []
    if current_run_id is not None:
        safe_current = _safe(current_run_id)
        detail = gateway.run_detail(current_run_id)
        series = gateway.run_series(current_run_id)
        current_run = next(
            (
                run
                for run in gateway.recent_runs(evidence_date=evidence_date, limit=1000)
                if run.id == current_run_id
            ),
            RunListItem(
                id=detail.session.id,
                session_date=detail.session.session_date,
                start_time_local=detail.session.start_time_local,
                activity_name=detail.session.activity_name,
                distance_mi=detail.display.distance_mi,
                timer_time_s=detail.session.timer_time_s,
                pace_min_per_mi=detail.display.pace_min_per_mi,
                avg_heart_rate_bpm=detail.session.avg_heart_rate_bpm,
                hr_source=detail.session.hr_source,
            ),
        )
        context = _run_context(gateway, current_run, metric_by_date)
        current_dir = directory / "current" / safe_current
        _write(current_dir / "summary.md", run_summary_markdown(context))
        _write(current_dir / "laps.md", laps_markdown(context))
        cached_current = render_current_run_stack(plot_cache_dir, detail, series)
        image_dir = current_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        current_images = []
        for cached_image in cached_current:
            destination = image_dir / cached_image.name
            shutil.copy2(cached_image, destination)
            current_images.append(str(destination.resolve()))

    resolved: list[ArtifactRef] = []
    for ref in _refs(journal, transcript):
        safe_value = _safe(ref.value)
        if ref.kind == "run":
            detail = gateway.run_detail(ref.value)
            run = RunListItem(
                id=detail.session.id,
                session_date=detail.session.session_date,
                start_time_local=detail.session.start_time_local,
                activity_name=detail.session.activity_name,
                distance_mi=detail.display.distance_mi,
                timer_time_s=detail.session.timer_time_s,
                pace_min_per_mi=detail.display.pace_min_per_mi,
                avg_heart_rate_bpm=detail.session.avg_heart_rate_bpm,
                hr_source=detail.session.hr_source,
            )
            _export_run(
                gateway,
                run=run,
                destination=directory / "refs/runs" / safe_value,
                plot_cache_dir=plot_cache_dir,
                metric_by_date=metric_by_date,
            )
        elif ref.kind == "plot":
            source = plot_cache_dir / safe_value
            if not source.is_file():
                raise FileNotFoundError(f"Referenced plot not found: {ref.value}")
            destination = directory / "refs/plots" / safe_value
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        elif ref.kind == "review":
            review = repo.review(ref.value)
            content = (
                f"# Review {ref.value}\n\nReview not found.\n"
                if review is None
                else (
                    f"# Review {review.id}\n\n"
                    f"{review.content_md or 'Review has no completed content.'}\n"
                )
            )
            _write(directory / "refs/reviews" / f"{safe_value}.md", content)
        elif ref.kind == "date":
            _write_date_ref(gateway, directory / "refs/dates" / f"{safe_value}.md", ref.value)
        resolved.append(ref)

    if transcript is not None:
        _write(directory / "transcript.md", _transcript_markdown(transcript))
    _write(directory / "question.md", question_md.rstrip() + "\n")
    return WorkspaceManifest(
        directory=str(directory),
        current_images=current_images,
        historical_run_ids=[run.id for run in recent_runs],
        resolved_refs=resolved,
    )
