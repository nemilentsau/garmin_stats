"""HTTP translation layer for queued coach reviews, threads, and memory."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.bootstrap.container import build_container
from app.domains.coach.application.memory import (
    CURRENT_MEMORY_POLICY_VERSION,
    active_journal_entries,
)
from app.domains.coach.contracts import (
    CoachBriefResponse,
    CoachEnqueueResponse,
    CoachJob,
    CoachJournalResponse,
    CoachMessageCreateRequest,
    CoachMessagesResponse,
    CoachReview,
    CoachReviewsResponse,
    CoachRunReviewRequest,
    CoachStatusResponse,
    CoachThread,
    CoachThreadCreateRequest,
    CoachThreadsResponse,
)

router = APIRouter(prefix="/api/coach", tags=["coach"])


@router.get("/status", response_model=CoachStatusResponse)
def get_status() -> CoachStatusResponse:
    container = build_container()
    return CoachStatusResponse(
        worker_enabled=container.config.coach_worker_enabled,
        running_job=container.coach_repo.running_job(),
        queued_count=container.coach_repo.queued_count(),
    )


@router.get("/reviews", response_model=CoachReviewsResponse)
def get_reviews(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
) -> CoachReviewsResponse:
    for value in (from_date, to_date):
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise HTTPException(status_code=422, detail="Dates must use YYYY-MM-DD") from error
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="from must be on or before to")
    reviews = build_container().coach_repo.list_reviews(
        from_date=from_date, to_date=to_date, limit=limit
    )
    return CoachReviewsResponse(reviews=reviews)


@router.get("/run-reviews/{run_id}", response_model=CoachReview)
def get_run_review(run_id: str) -> CoachReview:
    review = build_container().coach_repo.review_for_run(run_id)
    if review is None:
        raise LookupError(f"No coach review for run: {run_id}")
    return review


@router.post("/reviews/run", response_model=CoachEnqueueResponse)
def post_run_review(request: CoachRunReviewRequest, response: Response) -> CoachEnqueueResponse:
    result = build_container().coach_jobs.enqueue_run_review(request.run_id)
    response.status_code = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
    return result


@router.get("/reviews/{review_id}", response_model=CoachReview)
def get_review(review_id: str) -> CoachReview:
    review = build_container().coach_repo.review(review_id)
    if review is None:
        raise LookupError(f"Unknown coach review: {review_id}")
    return review


@router.post("/reviews/{review_id}/retry", response_model=CoachJob, status_code=202)
def post_review_retry(review_id: str) -> CoachJob:
    container = build_container()
    review = container.coach_repo.review(review_id)
    if review is None:
        raise LookupError(f"Unknown coach review: {review_id}")
    if review.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed reviews can be retried")
    return container.coach_jobs.retry_job(review.job_id)


@router.post(
    "/reviews/{review_id}/regenerate",
    response_model=CoachJob,
    status_code=202,
)
def post_review_regenerate(review_id: str) -> CoachJob:
    container = build_container()
    review = container.coach_repo.review(review_id)
    if review is None:
        raise LookupError(f"Unknown coach review: {review_id}")
    if review.status != "complete":
        raise HTTPException(
            status_code=409,
            detail="Only complete reviews can be regenerated",
        )
    return container.coach_jobs.regenerate_review(review_id)


@router.get("/threads", response_model=CoachThreadsResponse)
def get_threads() -> CoachThreadsResponse:
    return CoachThreadsResponse(threads=build_container().coach_repo.list_threads())


@router.post("/threads", response_model=CoachThread, status_code=201)
def post_thread(request: CoachThreadCreateRequest) -> CoachThread:
    return build_container().coach_jobs.create_thread(request.title)


@router.get("/threads/{thread_id}/messages", response_model=CoachMessagesResponse)
def get_messages(thread_id: str) -> CoachMessagesResponse:
    container = build_container()
    if container.coach_repo.thread(thread_id) is None:
        raise LookupError(f"Unknown coach thread: {thread_id}")
    return CoachMessagesResponse(messages=container.coach_repo.messages_for(thread_id))


@router.post(
    "/threads/{thread_id}/messages",
    response_model=CoachEnqueueResponse,
    status_code=202,
)
def post_message(thread_id: str, request: CoachMessageCreateRequest) -> CoachEnqueueResponse:
    container = build_container()
    thread = container.coach_repo.thread(thread_id)
    if thread is None:
        raise LookupError(f"Unknown coach thread: {thread_id}")
    if thread.status != "open":
        raise HTTPException(status_code=409, detail="Coach thread is not open")
    return container.coach_jobs.enqueue_message(thread_id, request.content_md)


@router.post("/threads/{thread_id}/close", response_model=CoachJob, status_code=202)
def post_close(thread_id: str) -> CoachJob:
    container = build_container()
    thread = container.coach_repo.thread(thread_id)
    if thread is None:
        raise LookupError(f"Unknown coach thread: {thread_id}")
    if thread.status != "open":
        raise HTTPException(status_code=409, detail="Coach thread is already closing or closed")
    return container.coach_jobs.close_thread(thread_id)


@router.post("/threads/{thread_id}/retry-close", response_model=CoachJob, status_code=202)
def post_retry_close(thread_id: str) -> CoachJob:
    container = build_container()
    thread = container.coach_repo.thread(thread_id)
    if thread is None:
        raise LookupError(f"Unknown coach thread: {thread_id}")
    if thread.status != "close_failed":
        raise HTTPException(status_code=409, detail="Thread close has not failed")
    return container.coach_jobs.retry_close(thread_id)


@router.get("/jobs/{job_id}", response_model=CoachJob)
def get_job(job_id: str) -> CoachJob:
    job = build_container().coach_repo.job(job_id)
    if job is None:
        raise LookupError(f"Unknown coach job: {job_id}")
    return job


@router.get("/brief", response_model=CoachBriefResponse)
def get_brief() -> CoachBriefResponse:
    brief = build_container().coach_repo.current_brief(
        policy_version=CURRENT_MEMORY_POLICY_VERSION
    )
    return CoachBriefResponse(brief=brief)


@router.get("/journal", response_model=CoachJournalResponse)
def get_journal(limit: int = Query(30, ge=1, le=200)) -> CoachJournalResponse:
    entries = build_container().coach_repo.list_journal(
        limit=limit,
        policy_version=CURRENT_MEMORY_POLICY_VERSION,
    )
    return CoachJournalResponse(entries=active_journal_entries(entries))
