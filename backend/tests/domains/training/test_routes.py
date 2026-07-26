"""Training route dependency propagation tests."""

from datetime import date as Date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.domains.training.routes as routes
from app.bootstrap.app import create_app
from app.domains.training.application.read_models import TrainingLogUpdateRequest
from app.domains.training.contracts import (
    TrainingCardLog,
    TrainingScheduleWindow,
    TrainingTodayResponse,
)


class _CoachJobsSpy:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str]] = []

    def enqueue_submitted_run_feedback(self, date: str, occurrence_key: str) -> None:
        self.submissions.append((date, occurrence_key))


def test_today_route_propagates_run_and_assessment_ports(monkeypatch):
    repo = object()
    run_port = object()
    assessment_port = object()
    captured: dict[str, object] = {}

    def fake_today(
        training_repo,
        *,
        date: str,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        captured.update(
            repo=training_repo,
            date=date,
            run_activity_port=run_activity_port,
            measurement_assessment_port=measurement_assessment_port,
        )
        return TrainingTodayResponse(date=date, cards=[])

    monkeypatch.setattr(routes, "get_training_today", fake_today)
    monkeypatch.setattr(
        routes,
        "build_container",
        lambda: SimpleNamespace(
            training_repo=repo,
            training_run_activity_port=run_port,
            training_measurement_assessment_port=assessment_port,
        ),
    )

    response = routes.get_today(date=Date(2026, 7, 17))

    assert response.date == "2026-07-17"
    assert captured == {
        "repo": repo,
        "date": "2026-07-17",
        "run_activity_port": run_port,
        "measurement_assessment_port": assessment_port,
    }


def test_schedule_route_propagates_run_and_assessment_ports(monkeypatch):
    repo = object()
    run_port = object()
    assessment_port = object()
    captured: dict[str, object] = {}

    def fake_window(
        training_repo,
        *,
        start_date: str,
        duration_days: int,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        captured.update(
            repo=training_repo,
            start_date=start_date,
            duration_days=duration_days,
            run_activity_port=run_activity_port,
            measurement_assessment_port=measurement_assessment_port,
        )
        return TrainingScheduleWindow(
            start_date=start_date,
            end_date=start_date,
            days=[],
        )

    monkeypatch.setattr(routes, "get_training_schedule_window", fake_window)
    monkeypatch.setattr(
        routes,
        "build_container",
        lambda: SimpleNamespace(
            training_repo=repo,
            training_run_activity_port=run_port,
            training_measurement_assessment_port=assessment_port,
        ),
    )

    response = routes.get_schedule_window(start=Date(2026, 7, 17), days=1)

    assert response.start_date == "2026-07-17"
    assert captured == {
        "repo": repo,
        "start_date": "2026-07-17",
        "duration_days": 1,
        "run_activity_port": run_port,
        "measurement_assessment_port": assessment_port,
    }


def test_log_route_propagates_ports_without_enqueuing_feedback_autosave(monkeypatch):
    repo = object()
    run_port = object()
    assessment_port = object()
    coach_jobs = _CoachJobsSpy()
    captured: dict[str, object] = {}

    def fake_upsert(
        training_repo,
        *,
        date: str,
        occurrence_key: str,
        update: TrainingLogUpdateRequest,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        captured.update(
            repo=training_repo,
            date=date,
            occurrence_key=occurrence_key,
            update=update,
            run_activity_port=run_activity_port,
            measurement_assessment_port=measurement_assessment_port,
        )
        return TrainingCardLog(
            id=f"{date}:{occurrence_key}",
            date=date,
            occurrence_key=occurrence_key,
        )

    monkeypatch.setattr(routes, "upsert_training_log", fake_upsert)
    monkeypatch.setattr(
        routes,
        "build_container",
        lambda: SimpleNamespace(
            training_repo=repo,
            training_run_activity_port=run_port,
            training_measurement_assessment_port=assessment_port,
            coach_jobs=coach_jobs,
        ),
    )
    update = TrainingLogUpdateRequest(notes="Saved")

    response = routes.put_today_card_log(
        date=Date(2026, 7, 20),
        occurrence_key="running.v3:run.lthr_test:d08",
        request=update,
    )

    assert response.notes is None
    assert captured == {
        "repo": repo,
        "date": "2026-07-20",
        "occurrence_key": "running.v3:run.lthr_test:d08",
        "update": update,
        "run_activity_port": run_port,
        "measurement_assessment_port": assessment_port,
    }
    assert coach_jobs.submissions == []


def test_log_route_never_enqueues_coach_after_explicit_completion_submission(monkeypatch):
    repo = object()
    run_port = object()
    assessment_port = object()
    coach_jobs = _CoachJobsSpy()
    occurrence_key = "running.v3:run.lthr_test:d08"

    def fake_upsert(
        training_repo,
        *,
        date: str,
        occurrence_key: str,
        update: TrainingLogUpdateRequest,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        del training_repo, run_activity_port, measurement_assessment_port
        return TrainingCardLog(
            id=f"{date}:{occurrence_key}",
            date=date,
            occurrence_key=occurrence_key,
            status=update.status or "pending",
            notes=update.notes,
        )

    monkeypatch.setattr(routes, "upsert_training_log", fake_upsert)
    monkeypatch.setattr(
        routes,
        "build_container",
        lambda: SimpleNamespace(
            training_repo=repo,
            training_run_activity_port=run_port,
            training_measurement_assessment_port=assessment_port,
            coach_jobs=coach_jobs,
        ),
    )

    response = routes.put_today_card_log(
        date=Date(2026, 7, 20),
        occurrence_key=occurrence_key,
        request=TrainingLogUpdateRequest(
            status="completed",
            notes="Felt controlled",
        ),
    )

    assert response.status == "completed"
    assert coach_jobs.submissions == []


def test_schedule_window_days_query_is_bounded_to_60(monkeypatch):
    def fake_window(
        training_repo,
        *,
        start_date: str,
        duration_days: int,
        run_activity_port=None,
        measurement_assessment_port=None,
    ):
        del training_repo, run_activity_port, measurement_assessment_port
        return TrainingScheduleWindow(start_date=start_date, end_date=start_date, days=[])

    monkeypatch.setattr(routes, "get_training_schedule_window", fake_window)
    monkeypatch.setattr(
        routes,
        "build_container",
        lambda: SimpleNamespace(
            training_repo=object(),
            training_run_activity_port=object(),
            training_measurement_assessment_port=object(),
        ),
    )
    client = TestClient(create_app())

    over_limit = client.get(
        "/api/training/schedule-window", params={"start": "2026-07-17", "days": 100000}
    )
    at_limit = client.get(
        "/api/training/schedule-window", params={"start": "2026-07-17", "days": 60}
    )

    assert over_limit.status_code == 422
    assert at_limit.status_code == 200


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", "/api/training/today?date=not-a-date"),
        ("get", "/api/training/schedule-window?start=not-a-date"),
        ("put", "/api/training/today/not-a-date/cards/card-1"),
    ],
)
def test_training_date_boundaries_reject_malformed_dates(method: str, url: str):
    client = TestClient(create_app())

    response = client.request(method, url, json={} if method == "put" else None)

    assert response.status_code == 422
