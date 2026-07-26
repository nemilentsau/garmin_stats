"""SQLite schema owned by the coach domain."""

from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS coach_reviews (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    kind TEXT NOT NULL,
    run_id TEXT,
    occurrence_key TEXT,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    assessment_effective_at TEXT,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coach_threads (
    id TEXT PRIMARY KEY,
    review_id TEXT,
    status TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coach_review_revisions (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL,
    UNIQUE(review_id, version)
);
CREATE INDEX IF NOT EXISTS idx_coach_review_revisions_review
    ON coach_review_revisions(review_id, version);
CREATE TABLE IF NOT EXISTS coach_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_coach_messages_thread
    ON coach_messages(thread_id, created_at, id);
CREATE TABLE IF NOT EXISTS coach_journal (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_coach_journal_ts
    ON coach_journal(ts, id);
CREATE TABLE IF NOT EXISTS coach_brief_versions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coach_jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL,
    available_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_coach_jobs_claim
    ON coach_jobs(status, priority, created_at, available_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_coach_reviews_run
    ON coach_reviews(run_id) WHERE kind = 'run';
"""


def init_coach_schema(connection: sqlite3.Connection) -> None:
    """Create coach-owned tables and indexes in a caller-managed connection."""
    connection.executescript(_SCHEMA)
    thread_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(coach_threads)")
    }
    if "review_id" not in thread_columns:
        connection.execute("ALTER TABLE coach_threads ADD COLUMN review_id TEXT")
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_coach_threads_review
        ON coach_threads(review_id) WHERE review_id IS NOT NULL
        """
    )
    review_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(coach_reviews)")
    }
    if "completed_at" in review_columns and "assessment_effective_at" not in review_columns:
        # An earlier run of this branch created the column under its original
        # name (`completed_at`) before it was renamed to `assessment_effective_at`.
        # Rename in place rather than re-deriving: the live DB otherwise has
        # zero `coach_reviews` rows, so this only protects branch-local dev DBs.
        connection.execute(
            "ALTER TABLE coach_reviews RENAME COLUMN completed_at TO assessment_effective_at"
        )
        review_columns.discard("completed_at")
        review_columns.add("assessment_effective_at")
    if "assessment_effective_at" not in review_columns:
        connection.execute(
            "ALTER TABLE coach_reviews ADD COLUMN assessment_effective_at TEXT"
        )
    # `assessment_effective_at` freezes the instant the review's current
    # measurement-assessment status first appeared (first completion if the
    # review has no assessment, or if its assessment's status hasn't changed
    # since). `updated_at` moves with every revision, and measurement history
    # re-derives past days against a per-day cutoff, so a mutable instant would
    # rewrite decisions that were already made -- see `_save_review` for the
    # status-based comparison that decides when this must move. Backfill
    # prefers revision 1 (the first completion snapshot) and falls back to
    # `updated_at` for pre-revision rows. Idempotent by construction: a second
    # run finds no NULL `assessment_effective_at` to fill.
    connection.execute(
        """
        UPDATE coach_reviews
        SET assessment_effective_at = COALESCE(
            (
                SELECT revision.created_at FROM coach_review_revisions AS revision
                WHERE revision.review_id = coach_reviews.id AND revision.version = 1
            ),
            updated_at
        )
        WHERE assessment_effective_at IS NULL AND status = 'complete'
        """
    )
    connection.execute("DROP INDEX IF EXISTS idx_coach_reviews_skip")
    connection.execute("DROP TABLE IF EXISTS coach_reconciliation_state")
    # `CoachReview` dropped the legacy `plots_viewed` field (superseded by persisted
    # `follow_up_questions`). Strict `extra="forbid"` validation would otherwise reject
    # any pre-existing row that still carries the key. Idempotent by construction: a
    # second run finds no matching rows and updates nothing.
    connection.execute(
        """
        UPDATE coach_reviews
        SET data = json_remove(data, '$.plots_viewed')
        WHERE json_extract(data, '$.plots_viewed') IS NOT NULL
        """
    )
