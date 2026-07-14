"""Strict contracts for coach API, persistence, queue, memory, and model output."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.contracts.base import StrictDefaultsRequired

ArtifactKind = Literal["run", "plot", "review", "date"]
ReviewKind = Literal["run", "skip"]
ReviewStatus = Literal["queued", "generating", "complete", "failed"]
ThreadStatus = Literal["open", "closing", "closed", "close_failed"]
JobKind = Literal["review_run", "review_skip", "chat_turn", "distill_thread"]
JobStatus = Literal["queued", "running", "complete", "failed"]
LegacyReviewVerdict = Literal[
    "compliant",
    "partial",
    "non_compliant",
    "skipped",
    "unplanned",
]
ReviewOutcome = Literal[
    "completed_as_intended",
    "completed_with_material_deviation",
    "not_completed",
    "skipped",
    "unplanned",
]
ReviewConfidence = Literal["low", "moderate", "high"]
HistoricalRole = Literal[
    "same_purpose",
    "recent_clean",
    "counterexample",
    "plan_anchor",
]


class ArtifactRef(StrictDefaultsRequired):
    kind: ArtifactKind
    value: str


class HistoricalEvidenceUse(StrictDefaultsRequired):
    run_id: str
    role: HistoricalRole
    reason: str = Field(min_length=1, max_length=300)
    refs: list[ArtifactRef] = Field(min_length=1, max_length=4)


class RunJournalSummary(StrictDefaultsRequired):
    purpose: str = Field(min_length=1, max_length=240)
    outcome: ReviewOutcome
    takeaway: str = Field(min_length=1, max_length=600)
    decision_relevant_uncertainties: list[str] = Field(max_length=3)
    follow_up_triggers: list[str] = Field(max_length=2)
    comparison_tags: list[str] = Field(max_length=6)
    refs: list[ArtifactRef] = Field(min_length=1, max_length=8)


class BriefUpdate(StrictDefaultsRequired):
    action: Literal["keep", "replace"]
    content_md: str | None = Field(default=None, max_length=6000)

    @model_validator(mode="after")
    def _content_matches_action(self) -> BriefUpdate:
        if self.action == "keep" and self.content_md is not None:
            raise ValueError("keep brief updates cannot contain content")
        if self.action == "replace" and not (self.content_md or "").strip():
            raise ValueError("replace brief updates require non-blank content")
        return self


class CoachMeasurementAssessment(StrictDefaultsRequired):
    """Coach judgment for one exact scheduled measurement-run occurrence."""

    run_id: str
    occurrence_key: str
    status: Literal["valid", "provisional", "failed"]
    rationale: str = Field(min_length=1, max_length=1000)

    @field_validator("rationale")
    @classmethod
    def _rationale_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rationale must contain non-whitespace text")
        return value


class CoachMeasurementAssessmentRecord(StrictDefaultsRequired):
    """Assessment plus the durable review/message record that supplied it."""

    assessment: CoachMeasurementAssessment
    source_id: str
    created_at: str


class CoachReview(StrictDefaultsRequired):
    id: str
    date: str
    kind: ReviewKind
    run_id: str | None = None
    occurrence_key: str | None = None
    status: ReviewStatus
    verdict: LegacyReviewVerdict | None = None
    outcome: ReviewOutcome | None = None
    confidence: ReviewConfidence | None = None
    content_md: str | None = None
    refs: list[ArtifactRef] = []
    plots_viewed: list[str] = []
    history_used: list[HistoricalEvidenceUse] = []
    measurement_assessment: CoachMeasurementAssessment | None = None
    job_id: str
    error: str | None = None
    created_at: str
    updated_at: str


class CoachThread(StrictDefaultsRequired):
    id: str
    title: str
    status: ThreadStatus
    codex_session_id: str | None = None
    created_at: str
    last_activity_at: str


class CoachMessage(StrictDefaultsRequired):
    id: str
    thread_id: str
    role: Literal["user", "coach", "system"]
    content_md: str
    refs: list[ArtifactRef] = []
    measurement_assessment: CoachMeasurementAssessment | None = None
    job_id: str | None = None
    created_at: str


class JournalEntry(StrictDefaultsRequired):
    id: str
    ts: str
    kind: Literal["review", "chat", "admonish"]
    content_md: str = Field(max_length=1600)
    refs: list[ArtifactRef] = []
    source_id: str
    policy_version: int = 1
    supersedes_id: str | None = None
    run_summary: RunJournalSummary | None = None


class BriefVersion(StrictDefaultsRequired):
    id: str
    content_md: str = Field(max_length=6000)
    source_id: str
    created_at: str
    policy_version: int = 1


class CoachJob(StrictDefaultsRequired):
    id: str
    kind: JobKind
    dedupe_key: str
    priority: int
    status: JobStatus
    payload: dict[str, object]
    attempt_count: int = 0
    available_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class CoachReconciliationState(StrictDefaultsRequired):
    activation_date: str
    initial_backfill_done: bool


class InitialReviewCandidate(StrictDefaultsRequired):
    kind: ReviewKind
    date: str
    run_id: str | None = None
    occurrence_key: str | None = None
    card_name: str | None = None


class ReviewOutput(StrictDefaultsRequired):
    outcome: ReviewOutcome
    confidence: ReviewConfidence
    review_md: str = Field(min_length=1, max_length=12000)
    follow_up_questions: list[str] = Field(max_length=2)
    history_used: list[HistoricalEvidenceUse]
    plots_viewed: list[str]
    refs: list[ArtifactRef]
    journal: RunJournalSummary
    brief_update: BriefUpdate
    measurement_assessment: CoachMeasurementAssessment | None = None


class ChatOutput(StrictDefaultsRequired):
    answer_md: str = Field(min_length=1, max_length=12000)
    refs: list[ArtifactRef]
    measurement_assessment: CoachMeasurementAssessment | None = None


class DistillOutput(StrictDefaultsRequired):
    journal_entry_md: str = Field(min_length=1, max_length=1600)
    refs: list[ArtifactRef]
    brief_update: BriefUpdate


class CoachEnqueueResponse(StrictDefaultsRequired):
    created: bool
    job: CoachJob
    review: CoachReview | None = None
    message: CoachMessage | None = None


class CoachReviewsResponse(StrictDefaultsRequired):
    reviews: list[CoachReview] = []


class CoachThreadsResponse(StrictDefaultsRequired):
    threads: list[CoachThread] = []


class CoachMessagesResponse(StrictDefaultsRequired):
    messages: list[CoachMessage] = []


class CoachJournalResponse(StrictDefaultsRequired):
    entries: list[JournalEntry] = []


class CoachBriefResponse(StrictDefaultsRequired):
    brief: BriefVersion | None = None


class CoachStatusResponse(StrictDefaultsRequired):
    worker_enabled: bool
    running_job: CoachJob | None = None
    queued_count: int


class CoachRunReviewRequest(StrictDefaultsRequired):
    run_id: str


class CoachThreadCreateRequest(StrictDefaultsRequired):
    title: str = Field(min_length=1, max_length=120)


class CoachMessageCreateRequest(StrictDefaultsRequired):
    content_md: str = Field(min_length=1, max_length=12000)
