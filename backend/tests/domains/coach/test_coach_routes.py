"""HTTP contract tests for queued coach operations; no Codex execution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

import app.domains.coach.routes as routes
from app.bootstrap.app import create_app
from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.jobs import CoachJobs
from app.domains.coach.contracts import (
    ArtifactRef,
    BriefUpdate,
    ReviewOutput,
    RunJournalSummary,
)
from app.domains.coach.read_gateway import CoachReadGateway
from app.domains.training.contracts import TrainingTodayResponse


class FakeGateway:
    def run_detail(self, run_id: str):
        from tests.domains.coach.test_coach_context import _detail

        detail = _detail()
        return detail.model_copy(
            update={"session": detail.session.model_copy(update={"id": run_id})}
        )

    def training_today(self, target: str) -> TrainingTodayResponse:
        return TrainingTodayResponse(date=target, cards=[])


def _complete_review(repo: SqliteCoachRepository):
    review, _, _ = repo.enqueue_run_review(
        run_id="run-complete", date="2026-07-12", occurrence_key="run-am"
    )
    job = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert job is not None
    repo.mark_review_generating(review.id, updated_at="2026-07-12T12:00:00Z")
    run_ref = ArtifactRef(kind="run", value="run-complete")
    repo.complete_review_output(
        review_id=review.id,
        job_id=job.id,
        output=ReviewOutput(
            outcome="completed_as_intended",
            confidence="high",
            review_md="Purpose achieved.",
            follow_up_questions=[],
            history_used=[],
            plots_viewed=[],
            refs=[run_ref],
            journal=RunJournalSummary(
                purpose="Easy aerobic maintenance",
                outcome="completed_as_intended",
                takeaway="Purpose achieved.",
                decision_relevant_uncertainties=[],
                follow_up_triggers=[],
                comparison_tags=["easy"],
                refs=[run_ref],
            ),
            brief_update=BriefUpdate(action="keep", content_md=None),
        ),
        finished_at="2026-07-12T12:01:00Z",
    )
    return review, job


@pytest.fixture
def coach_client(monkeypatch):
    repo = SqliteCoachRepository()
    gateway = cast(CoachReadGateway, FakeGateway())
    jobs = CoachJobs(repo=repo, gateway=gateway, local_today=lambda: "2026-07-12")
    container = SimpleNamespace(
        config=SimpleNamespace(coach_worker_enabled=False),
        coach_repo=repo,
        coach_jobs=jobs,
    )
    monkeypatch.setattr(routes, "build_container", lambda: container)
    return TestClient(create_app()), repo


def test_manual_run_review_enqueues_and_duplicate_returns_existing(coach_client):
    client, repo = coach_client

    first = client.post("/api/coach/reviews/run", json={"run_id": "run-1"})
    second = client.post("/api/coach/reviews/run", json={"run_id": "run-1"})

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["review"]["id"] == second.json()["review"]["id"]
    assert repo.queued_count() == 1


def test_status_lookup_and_review_filters(coach_client):
    client, _repo = coach_client
    created = client.post("/api/coach/reviews/run", json={"run_id": "run-1"}).json()

    status = client.get("/api/coach/status")
    lookup = client.get(f"/api/coach/reviews/{created['review']['id']}")
    by_run = client.get("/api/coach/run-reviews/run-1")
    listed = client.get("/api/coach/reviews?from=2026-07-11&to=2026-07-11&limit=1")

    assert status.json() == {"worker_enabled": False, "running_job": None, "queued_count": 1}
    assert lookup.status_code == 200
    assert by_run.json()["run_id"] == "run-1"
    assert len(listed.json()["reviews"]) == 1
    assert client.get("/api/coach/reviews?from=2026-07-12&to=2026-07-11").status_code == 422
    assert client.get("/api/coach/reviews?limit=201").status_code == 422


def test_failed_review_retry_and_conflict_for_nonfailed(coach_client):
    client, repo = coach_client
    created = client.post("/api/coach/reviews/run", json={"run_id": "run-1"}).json()
    review = created["review"]

    assert client.post(f"/api/coach/reviews/{review['id']}/retry").status_code == 409
    claimed = repo.claim_next_job("9999-01-01T00:00:00Z")
    assert claimed is not None
    repo.fail_job(claimed.id, error="bad output", finished_at="2026-07-12T12:00:00Z")

    retried = client.post(f"/api/coach/reviews/{review['id']}/retry")

    assert retried.status_code == 202
    assert retried.json()["id"] == claimed.id
    assert retried.json()["status"] == "queued"


def test_complete_review_regenerates_and_noncomplete_conflicts(coach_client):
    client, repo = coach_client
    review, job = _complete_review(repo)
    queued = client.post("/api/coach/reviews/run", json={"run_id": "run-queued"}).json()
    assert (
        client.post(
            f"/api/coach/reviews/{queued['review']['id']}/regenerate"
        ).status_code
        == 409
    )
    regenerated = client.post(f"/api/coach/reviews/{review.id}/regenerate")

    assert regenerated.status_code == 202
    assert regenerated.json()["id"] == job.id
    assert regenerated.json()["status"] == "queued"
    assert regenerated.json()["attempt_count"] == 1


def test_thread_message_listing_close_and_closed_conflicts(coach_client):
    client, repo = coach_client
    thread = client.post("/api/coach/threads", json={"title": "Recovery"})
    thread_id = thread.json()["id"]

    message = client.post(
        f"/api/coach/threads/{thread_id}/messages", json={"content_md": "What next?"}
    )
    messages = client.get(f"/api/coach/threads/{thread_id}/messages")
    close = client.post(f"/api/coach/threads/{thread_id}/close")

    assert thread.status_code == 201
    assert message.status_code == 202
    assert messages.json()["messages"][0]["content_md"] == "What next?"
    assert close.status_code == 202
    assert repo.thread(thread_id).status == "closing"  # type: ignore[union-attr]
    assert (
        client.post(
            f"/api/coach/threads/{thread_id}/messages", json={"content_md": "Again"}
        ).status_code
        == 409
    )
    assert client.post(f"/api/coach/threads/{thread_id}/close").status_code == 409


def test_unknown_resources_strict_requests_and_artifact_routes(coach_client):
    client, _repo = coach_client

    assert client.get("/api/coach/reviews/missing").status_code == 404
    assert client.get("/api/coach/run-reviews/missing").status_code == 404
    assert client.get("/api/coach/jobs/missing").status_code == 404
    assert client.get("/api/coach/threads/missing/messages").status_code == 404
    strict = client.post(
        "/api/coach/reviews/run", json={"run_id": "x", "date": "bad"}
    )
    assert strict.status_code == 422
    assert client.get("/api/assistant/artifacts").status_code == 200
