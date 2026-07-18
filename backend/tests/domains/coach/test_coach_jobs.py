"""Tests for coach enqueue policy, reconciliation, and idle lifecycle."""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.jobs import CoachJobs
from app.domains.coach.contracts import CoachThread
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.garmin_analytics.contracts import RunListItem
from app.domains.training.contracts import TrainingTodayResponse

NOW = "2026-07-12T12:00:00Z"


class ReconcileGateway:
    def __init__(self) -> None:
        self.runs: list[RunListItem] = []
        self.days: dict[str, TrainingTodayResponse] = {}
        self.training_today_calls: dict[str, int] = {}

    def recent_runs(self, *, evidence_date: str, limit: int = 20):
        return [run for run in reversed(self.runs) if run.session_date <= evidence_date][:limit]

    def training_today(self, target: str) -> TrainingTodayResponse:
        self.training_today_calls[target] = self.training_today_calls.get(target, 0) + 1
        return self.days.get(target, TrainingTodayResponse(date=target, cards=[]))

    def run_detail(self, run_id: str):
        from tests.domains.coach.test_coach_context import _detail

        return _detail().model_copy(
            update={"session": _detail().session.model_copy(update={"id": run_id})}
        )


def _run(run_id: str, target: str) -> RunListItem:
    return RunListItem(id=run_id, session_date=target, start_time_local=f"{target}T06:00:00")


def _jobs(repo: SqliteCoachRepository, gateway: ReconcileGateway) -> CoachJobs:
    return CoachJobs(
        repo=repo,
        gateway=cast(CoachReadGateway, gateway),
        local_today=lambda: "2026-07-12",
    )


def test_initial_reconcile_caps_three_most_recent_and_orders_oldest_first():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.runs = [
        _run(f"run-{offset}", (date(2026, 7, 12) - timedelta(days=offset)).isoformat())
        for offset in range(5)
    ]
    jobs = _jobs(repo, gateway)

    created = jobs.reconcile_pending()

    assert len(created) == 3
    reviews = repo.list_reviews(from_date=None, to_date=None, limit=10)
    assert {review.run_id for review in reviews} == {"run-0", "run-1", "run-2"}
    claimed = [repo.claim_next_job("9999-01-01T00:00:00Z") for _ in range(3)]
    assert [job.payload["run_id"] for job in claimed if job is not None] == [
        "run-2",
        "run-1",
        "run-0",
    ]


def test_second_reconcile_does_not_drain_pre_activation_backlog_or_duplicate():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.runs = [
        _run(f"run-{offset}", (date(2026, 7, 12) - timedelta(days=offset)).isoformat())
        for offset in range(5)
    ]
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()

    assert jobs.reconcile_pending() == []
    assert len(repo.list_reviews(from_date=None, to_date=None, limit=10)) == 3


def test_initial_window_includes_exact_fourteen_day_boundary_only():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.runs = [_run("boundary", "2026-06-28"), _run("older", "2026-06-27")]
    jobs = _jobs(repo, gateway)

    jobs.reconcile_pending()

    assert repo.review_for_run("boundary") is not None
    assert repo.review_for_run("older") is None


def test_reconcile_uses_training_run_classification_not_bundle_literal():
    from tests.domains.coach.test_coach_context import _card

    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    semantic_non_run = _card([], status="pending").model_copy(update={"is_running": False})
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[semantic_non_run],
    )

    created = _jobs(repo, gateway).reconcile_pending()

    assert created == []


def test_past_scheduled_run_waits_for_confirmed_activity_sync_coverage():
    from tests.domains.coach.test_coach_context import _card

    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[_card([], status="pending")],
    )
    jobs = CoachJobs(
        repo=repo,
        gateway=cast(CoachReadGateway, gateway),
        local_today=lambda: "2026-07-12",
        activity_date_covered=lambda _day: False,
    )

    created = jobs.reconcile_pending()

    assert created == []
    assert repo.list_reviews(from_date=None, to_date=None, limit=10) == []


def test_covered_past_scheduled_run_enqueues_one_skip_idempotently():
    from tests.domains.coach.test_coach_context import _card

    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[_card([], status="pending")],
    )
    jobs = CoachJobs(
        repo=repo,
        gateway=cast(CoachReadGateway, gateway),
        local_today=lambda: "2026-07-12",
        activity_date_covered=lambda day: day == "2026-07-11",
    )

    first = jobs.reconcile_pending()
    second = jobs.reconcile_pending()

    assert len(first) == 1
    assert first[0].kind == "review_skip"
    assert second == []


def test_ongoing_reconcile_includes_activation_day_run_and_dedupes_repeat_calls():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()
    gateway.runs = [_run("new", "2026-07-13"), _run("same-day", "2026-07-12")]
    jobs.local_today = lambda: "2026-07-13"

    first = jobs.reconcile_pending()
    second = jobs.reconcile_pending()

    assert {job.payload["run_id"] for job in first} == {"new", "same-day"}
    assert second == []
    assert repo.review_for_run("same-day") is not None


def test_activation_day_run_after_backfill_still_gets_reviewed():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()  # activation_date = 2026-07-12, no runs at backfill time

    gateway.runs = [_run("late-arrival", "2026-07-12")]
    created = jobs.reconcile_pending()

    assert len(created) == 1
    assert created[0].payload["run_id"] == "late-arrival"
    assert repo.review_for_run("late-arrival") is not None


def test_reconcile_projects_each_date_once():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()  # activation_date = 2026-07-12

    gateway.runs = [_run("run-a", "2026-07-13"), _run("run-b", "2026-07-13")]
    jobs.local_today = lambda: "2026-07-14"

    jobs.reconcile_pending()

    assert gateway.training_today_calls.get("2026-07-13") == 1


def test_reconcile_bounds_scan_to_lookback_window():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = CoachJobs(
        repo=repo,
        gateway=cast(CoachReadGateway, gateway),
        local_today=lambda: "2026-04-13",
    )
    jobs.reconcile_pending()  # activation_date = 2026-04-13 (90 days before the day below)

    gateway.training_today_calls = {}
    jobs.local_today = lambda: "2026-07-12"
    jobs.reconcile_pending()

    assert len(gateway.training_today_calls) <= 31


def test_manual_review_returns_existing_complete_review_without_duplicate():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)

    first = jobs.enqueue_run_review("run-1")
    second = jobs.enqueue_run_review("run-1")

    assert first.review is not None and second.review is not None
    assert first.review.id == second.review.id
    assert first.created is True
    assert second.created is False
    assert repo.queued_count() == 1


def test_idle_thread_boundary_queues_distill_and_just_under_stays_open():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    for thread_id, last_activity in (
        ("idle", "2026-07-12T06:00:00Z"),
        ("active", "2026-07-12T06:00:01Z"),
    ):
        repo.insert_thread(
            CoachThread(
                id=thread_id,
                title=thread_id,
                status="open",
                created_at=NOW,
                last_activity_at=last_activity,
            )
        )
    jobs = _jobs(repo, gateway)

    queued = jobs.reconcile_idle_threads(now=NOW)

    assert [job.payload["thread_id"] for job in queued] == ["idle"]
    assert repo.thread("idle").status == "closing"  # type: ignore[union-attr]
    assert repo.thread("active").status == "open"  # type: ignore[union-attr]
