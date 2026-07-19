"""Tests for coach enqueue policy, reconciliation, and idle lifecycle."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, cast

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.jobs import CoachJobs
from app.domains.coach.contracts import CoachThread
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.training.contracts import (
    TrainingExecutionEvaluation,
    TrainingRunActivitySummary,
    TrainingTodayResponse,
)

NOW = "2026-07-12T12:00:00Z"


class ReconcileGateway:
    def __init__(self) -> None:
        self.days: dict[str, TrainingTodayResponse] = {}
        self.training_today_calls: dict[str, int] = {}

    def training_today(self, target: str) -> TrainingTodayResponse:
        self.training_today_calls[target] = self.training_today_calls.get(target, 0) + 1
        return self.days.get(target, TrainingTodayResponse(date=target, cards=[]))

    def run_detail(self, run_id: str):
        from tests.domains.coach.test_coach_context import _detail

        return _detail().model_copy(
            update={"session": _detail().session.model_copy(update={"id": run_id})}
        )

def _jobs(repo: SqliteCoachRepository, gateway: ReconcileGateway) -> CoachJobs:
    return CoachJobs(
        repo=repo,
        gateway=cast(CoachReadGateway, gateway),
        local_today=lambda: "2026-07-12",
        activity_date_covered=lambda _day: True,
    )


def _pending_run_card(target: str, suffix: str = "run"):
    from tests.domains.coach.test_coach_context import _card

    return _card([], status="pending").model_copy(
        update={
            "date": target,
            "occurrence_key": f"running.v3:run.easy:{suffix}",
        }
    )


def _associated_run_card(
    target: str,
    *,
    source: Literal["manual_log", "tracked_run", "none"],
    run_id: str = "run-1",
    suffix: str = "run",
):
    return _pending_run_card(target, suffix=suffix).model_copy(
        update={
            "status": "completed",
            "execution": TrainingExecutionEvaluation(
                status="completed",
                source=source,
                run_id=run_id,
            ),
            "associated_activity": TrainingRunActivitySummary(
                run_id=run_id,
                session_date=target,
                start_time_local=f"{target}T06:00:00",
            ),
        }
    )


def test_initial_reconcile_caps_three_most_recent_skips_and_orders_oldest_first():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    for offset in range(1, 6):
        target = (date(2026, 7, 12) - timedelta(days=offset)).isoformat()
        gateway.days[target] = TrainingTodayResponse(
            date=target,
            cards=[_pending_run_card(target, suffix=f"d{offset}")],
        )
    jobs = _jobs(repo, gateway)

    created = jobs.reconcile_pending()

    assert len(created) == 3
    reviews = repo.list_reviews(from_date=None, to_date=None, limit=10)
    assert {review.date for review in reviews} == {
        "2026-07-09",
        "2026-07-10",
        "2026-07-11",
    }
    claimed = [repo.claim_next_job("9999-01-01T00:00:00Z") for _ in range(3)]
    assert [job.payload["date"] for job in claimed if job is not None] == [
        "2026-07-09",
        "2026-07-10",
        "2026-07-11",
    ]


def test_second_reconcile_does_not_drain_pre_activation_backlog_or_duplicate():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    for offset in range(1, 6):
        target = (date(2026, 7, 12) - timedelta(days=offset)).isoformat()
        gateway.days[target] = TrainingTodayResponse(
            date=target,
            cards=[_pending_run_card(target, suffix=f"d{offset}")],
        )
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()

    assert jobs.reconcile_pending() == []
    assert len(repo.list_reviews(from_date=None, to_date=None, limit=10)) == 3


def test_initial_window_includes_exact_fourteen_day_boundary_only():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.days = {
        "2026-06-28": TrainingTodayResponse(
            date="2026-06-28",
            cards=[_pending_run_card("2026-06-28", suffix="boundary")],
        ),
        "2026-06-27": TrainingTodayResponse(
            date="2026-06-27",
            cards=[_pending_run_card("2026-06-27", suffix="older")],
        ),
    }
    jobs = _jobs(repo, gateway)

    jobs.reconcile_pending()

    reviews = repo.list_reviews(from_date=None, to_date=None, limit=10)
    assert [review.date for review in reviews] == ["2026-06-28"]


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
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[_pending_run_card("2026-07-11")],
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
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[_pending_run_card("2026-07-11")],
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


def test_ongoing_reconcile_includes_activation_day_skip_and_dedupes_repeat_calls():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()
    gateway.days["2026-07-12"] = TrainingTodayResponse(
        date="2026-07-12",
        cards=[_pending_run_card("2026-07-12", suffix="activation")],
    )
    jobs.local_today = lambda: "2026-07-13"

    first = jobs.reconcile_pending()
    second = jobs.reconcile_pending()

    assert [job.payload["date"] for job in first] == ["2026-07-12"]
    assert second == []


def test_reconcile_does_not_enqueue_tracked_run_before_feedback_submission():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()
    gateway.days["2026-07-12"] = TrainingTodayResponse(
        date="2026-07-12",
        cards=[
            _associated_run_card(
                "2026-07-12",
                source="tracked_run",
                run_id="uploaded",
            )
        ],
    )

    assert jobs.reconcile_pending() == []
    assert repo.review_for_run("uploaded") is None


def test_reconcile_recovers_submitted_feedback_after_immediate_enqueue_failure():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()
    gateway.days["2026-07-12"] = TrainingTodayResponse(
        date="2026-07-12",
        cards=[
            _associated_run_card(
                "2026-07-12",
                source="manual_log",
                run_id="submitted",
            )
        ],
    )

    first = jobs.reconcile_pending()
    second = jobs.reconcile_pending()

    assert [job.payload["run_id"] for job in first] == ["submitted"]
    assert second == []
    assert repo.review_for_run("submitted") is not None


def test_reconcile_projects_each_date_once():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    jobs = _jobs(repo, gateway)
    jobs.reconcile_pending()  # activation_date = 2026-07-12

    gateway.days["2026-07-13"] = TrainingTodayResponse(
        date="2026-07-13",
        cards=[
            _pending_run_card("2026-07-13", suffix="a"),
            _pending_run_card("2026-07-13", suffix="b"),
        ],
    )
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


def test_submitted_run_feedback_enqueues_associated_run_idempotently():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    occurrence_key = "running.v3:run.easy:d01"
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[
            _associated_run_card(
                "2026-07-11",
                source="manual_log",
                suffix="d01",
            ).model_copy(update={"occurrence_key": occurrence_key})
        ],
    )
    jobs = _jobs(repo, gateway)

    first = jobs.enqueue_submitted_run_feedback("2026-07-11", occurrence_key)
    second = jobs.enqueue_submitted_run_feedback("2026-07-11", occurrence_key)

    assert first is not None and first.created is True
    assert second is not None and second.created is False
    assert first.review is not None and first.review.run_id == "run-1"
    assert repo.queued_count() == 1


def test_submitted_feedback_without_associated_run_does_not_enqueue():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    card = _pending_run_card("2026-07-11")
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[card],
    )
    jobs = _jobs(repo, gateway)

    assert jobs.enqueue_submitted_run_feedback("2026-07-11", card.occurrence_key) is None
    assert repo.queued_count() == 0


def test_submitted_feedback_for_non_run_card_does_not_enqueue():
    repo = SqliteCoachRepository()
    gateway = ReconcileGateway()
    card = _pending_run_card("2026-07-11").model_copy(update={"is_running": False})
    gateway.days["2026-07-11"] = TrainingTodayResponse(
        date="2026-07-11",
        cards=[card],
    )
    jobs = _jobs(repo, gateway)

    assert jobs.enqueue_submitted_run_feedback("2026-07-11", card.occurrence_key) is None
    assert repo.queued_count() == 0


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
