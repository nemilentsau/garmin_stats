"""Training route dependency propagation tests."""

from types import SimpleNamespace

import app.domains.training.routes as routes
from app.domains.training.contracts import TrainingScheduleWindow, TrainingTodayResponse


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

    response = routes.get_today(date="2026-07-17")

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

    response = routes.get_schedule_window(start="2026-07-17", days=1)

    assert response.start_date == "2026-07-17"
    assert captured == {
        "repo": repo,
        "start_date": "2026-07-17",
        "duration_days": 1,
        "run_activity_port": run_port,
        "measurement_assessment_port": assessment_port,
    }
