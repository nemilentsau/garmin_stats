"""Strict contracts for coach API, persistence, queue, memory, and model output."""

from __future__ import annotations

import re
from datetime import date as _date
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.contracts.base import StrictDefaultsRequired

_SAFE_ARTIFACT_ID = re.compile(r"[A-Za-z0-9._-]+")


def safe_artifact_id(value: str) -> str:
    """Validate an artifact/thread identifier used in paths and refs.

    The single, strictest-union charset policy for every place coach code
    turns an id into a filesystem path segment or artifact reference:
    non-empty, charset-restricted to `[A-Za-z0-9._-]`, and never exactly `.`
    or `..` (which would otherwise resolve to a directory traversal).
    """
    if not value or value in {".", ".."} or _SAFE_ARTIFACT_ID.fullmatch(value) is None:
        raise ValueError(f"Unsafe artifact reference: {value}")
    return value


def require_monday_week_start(value: str) -> None:
    """Validate that `value` is a canonical ISO `YYYY-MM-DD` date that is a Monday.

    A week review's identity (dedupe key, stored date) is its Monday week-start,
    so this is a domain invariant, not just an HTTP request-shape check: it is
    enforced both at the route (translated to 422) and in the repository layer
    (`SqliteCoachRepository.enqueue_week_review`), so any other caller — a
    script, a future job — gets the same rejection. `date.fromisoformat` also
    accepts non-canonical ISO spellings that round-trip to the same calendar
    day but a different string (see `routes._canonical_date`), so canonical
    form is re-checked here too rather than assumed from an upstream check.
    """
    parsed = _date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"Not a canonical ISO date: {value}")
    if parsed.weekday() != 0:
        raise ValueError(f"week_start must be a Monday: {value}")


ArtifactKind = Literal["run", "plot", "review", "date"]
ReviewKind = Literal["run", "day", "week"]
ReviewStatus = Literal["queued", "generating", "complete", "failed"]
ThreadStatus = Literal["open", "closing", "closed", "close_failed"]
JobKind = Literal["review_run", "review_day", "review_week", "chat_turn", "distill_thread"]
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
    kind: ArtifactKind = Field(
        description="Durable reference type: run, plot, persisted review, or ISO date."
    )
    value: str = Field(
        description=(
            "Identifier only: run id, plot image basename, persisted review id, or ISO "
            "date. Never a workspace path, filename anchor, plan.md, or recovery.md."
        )
    )


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


class PlotObservation(StrictDefaultsRequired):
    """Decision-relevant visual evidence actually used by a review."""

    plot: str = Field(min_length=1, max_length=255)
    observation: str = Field(min_length=1, max_length=300)

    @field_validator("plot")
    @classmethod
    def _plot_is_basename(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("plot must be an image basename")
        return value

    @field_validator("observation")
    @classmethod
    def _observation_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("observation must contain non-whitespace text")
        return value


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
    headline: str | None = None
    content_md: str | None = None
    refs: list[ArtifactRef] = []
    follow_up_questions: list[str] = []
    plot_observations: list[PlotObservation] = []
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
    review_id: str | None = None
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


class ReviewOutput(StrictDefaultsRequired):
    headline: str = Field(min_length=1, max_length=160)
    outcome: ReviewOutcome
    confidence: ReviewConfidence
    review_md: str = Field(min_length=1, max_length=12000)
    follow_up_questions: list[str] = Field(max_length=3)
    history_used: list[HistoricalEvidenceUse]
    plot_observations: list[PlotObservation]
    refs: list[ArtifactRef]
    journal: RunJournalSummary
    brief_update: BriefUpdate
    measurement_assessment: CoachMeasurementAssessment | None = None


class ReviewRevisionOutput(StrictDefaultsRequired):
    """An explicit correction to the linked review, never an ordinary chat side effect."""

    headline: str = Field(min_length=1, max_length=160)
    content_md: str = Field(min_length=1, max_length=12000)
    outcome: ReviewOutcome
    confidence: ReviewConfidence
    refs: list[ArtifactRef]
    follow_up_questions: list[str] = Field(max_length=3)
    plot_observations: list[PlotObservation]
    history_used: list[HistoricalEvidenceUse]
    measurement_assessment: CoachMeasurementAssessment | None = None


class CoachReviewRevision(StrictDefaultsRequired):
    id: str
    review_id: str
    version: int = Field(ge=1)
    content_md: str
    outcome: ReviewOutcome
    confidence: ReviewConfidence
    refs: list[ArtifactRef]
    follow_up_questions: list[str] = []
    plot_observations: list[PlotObservation] = []
    history_used: list[HistoricalEvidenceUse] = []
    measurement_assessment: CoachMeasurementAssessment | None = None
    snapshot_complete: bool = False
    source_message_id: str | None = None
    created_at: str


class ChatOutput(StrictDefaultsRequired):
    answer_md: str = Field(min_length=1, max_length=12000)
    refs: list[ArtifactRef]
    measurement_assessment: CoachMeasurementAssessment | None = None
    review_revision: ReviewRevisionOutput | None = None


class WeekReviewOutput(StrictDefaultsRequired):
    """A weekly synthesis: no outcome/confidence/measurement axes — those are
    per-occurrence judgments a week-level review never makes."""

    headline: str = Field(min_length=1, max_length=160)
    synthesis_md: str = Field(min_length=1, max_length=12000)
    follow_up_questions: list[str] = Field(max_length=3)
    journal: RunJournalSummary
    brief_update: BriefUpdate
    refs: list[ArtifactRef]
    plot_observations: list[PlotObservation]
    history_used: list[HistoricalEvidenceUse]


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


class CoachReviewRevisionsResponse(StrictDefaultsRequired):
    revisions: list[CoachReviewRevision] = []


class CoachThreadsResponse(StrictDefaultsRequired):
    threads: list[CoachThread] = []


class CoachMessagesResponse(StrictDefaultsRequired):
    messages: list[CoachMessage] = []


class CoachBriefResponse(StrictDefaultsRequired):
    brief: BriefVersion | None = None


class CoachStatusResponse(StrictDefaultsRequired):
    worker_enabled: bool
    running_job: CoachJob | None = None
    queued_count: int


class CoachWatchItem(StrictDefaultsRequired):
    text: str
    source_id: str
    ts: str


class CoachJournalResponse(StrictDefaultsRequired):
    entries: list[JournalEntry]
    watch_items: list[CoachWatchItem]


class CoachRunReviewRequest(StrictDefaultsRequired):
    run_id: str


class CoachDayReviewRequest(StrictDefaultsRequired):
    date: str


class CoachWeekReviewRequest(StrictDefaultsRequired):
    week_start: str


class CoachThreadCreateRequest(StrictDefaultsRequired):
    title: str = Field(min_length=1, max_length=120)


class CoachMessageCreateRequest(StrictDefaultsRequired):
    content_md: str = Field(min_length=1, max_length=12000)
    review_revision_requested: bool = False
