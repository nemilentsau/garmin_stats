"""Context snapshot builder for assistant runs."""

from uuid import uuid4

from ..infra.database import (
    load_daily_checkins,
    load_daily_metrics,
    load_experiments,
    load_notes,
    load_routine_schedules,
    load_user_profile,
    save_context_snapshot,
)
from ..models import ContextSnapshot, DailyMetric
from ..utils.timeutil import now_iso
from .dashboard import load_dashboard_overview


def _metric_digest(metric: DailyMetric) -> dict[str, float | int | str | None]:
    return {
        "date": metric.date,
        "resting_hr": metric.heart_rate.resting,
        "hrv_nightly": metric.hrv.nightly_avg,
        "sleep_score": metric.sleep.score,
        "stress_avg": metric.stress.avg,
        "body_battery_min": metric.body_battery.min,
        "body_battery_max": metric.body_battery.max,
    }


def build_context_snapshot(window_days: int = 14) -> ContextSnapshot:
    """Build and persist a context snapshot for assistant use."""
    metrics = load_daily_metrics()
    recent_metrics = metrics[-window_days:]
    profile = load_user_profile()
    active_routines = load_routine_schedules(status="active")
    active_experiments = [
        experiment for experiment in load_experiments() if experiment.status in {"active", "draft"}
    ]
    recent_checkins = load_daily_checkins(last_n=7)
    recent_notes = load_notes(last_n=10)

    try:
        overview = load_dashboard_overview()
    except LookupError:
        overview = None

    latest_date = recent_metrics[-1].date if recent_metrics else None
    summary_lines = [
        "# Health Context Snapshot",
        f"- Latest date: {latest_date or 'n/a'}",
        f"- Recent metrics window: {len(recent_metrics)} days",
        f"- Active routines: {len(active_routines)}",
        f"- Active or draft experiments: {len(active_experiments)}",
        f"- Recent check-ins: {len(recent_checkins)}",
        f"- Recent notes: {len(recent_notes)}",
    ]
    if overview is not None and overview.readiness is not None:
        summary_lines.append(
            f"- Readiness: {overview.readiness.score} ({overview.readiness.label})"
        )

    snapshot = ContextSnapshot(
        id=f"snapshot-{uuid4().hex}",
        date_window_start=recent_metrics[0].date if recent_metrics else None,
        date_window_end=latest_date,
        created_at=now_iso(),
        snapshot_json={
            "profile": profile.model_dump() if profile is not None else None,
            "overview": overview.model_dump() if overview is not None else None,
            "recent_daily_metrics": [_metric_digest(metric) for metric in recent_metrics],
            "active_routines": [routine.model_dump() for routine in active_routines],
            "active_experiments": [experiment.model_dump() for experiment in active_experiments],
            "recent_checkins": [checkin.model_dump() for checkin in recent_checkins],
            "recent_notes": [note.model_dump() for note in recent_notes],
        },
        summary_markdown="\n".join(summary_lines),
    )
    save_context_snapshot(snapshot)
    return snapshot
