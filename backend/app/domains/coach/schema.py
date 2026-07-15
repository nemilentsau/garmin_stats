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
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coach_threads (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    data TEXT NOT NULL
);
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
CREATE TABLE IF NOT EXISTS coach_reconciliation_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    activation_date TEXT NOT NULL,
    initial_backfill_done INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_coach_reviews_run
    ON coach_reviews(run_id) WHERE kind = 'run';
CREATE UNIQUE INDEX IF NOT EXISTS idx_coach_reviews_skip
    ON coach_reviews(date, occurrence_key) WHERE kind = 'skip';
"""


def init_coach_schema(connection: sqlite3.Connection) -> None:
    """Create coach-owned tables and indexes in a caller-managed connection."""
    connection.executescript(_SCHEMA)
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
