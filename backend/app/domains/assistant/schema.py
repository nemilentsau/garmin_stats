"""SQLite schema for assistant conversation storage.

The assistant owns durable threads, messages, runs, evidence bundles, memory
records, and retained legacy planning/context tables. Migration code that
backfills lookup policy stays in the adapter because it depends on assistant
text-normalization rules.
"""

from __future__ import annotations

import sqlite3

_JSON_COLS = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS assistant_threads ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS context_snapshots ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS evidence_cards ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS plans ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_runs (
    id TEXT PRIMARY KEY,
    thread_id TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_evidence_bundles (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    user_message_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_memory_records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    entity_id TEXT,
    alias_text TEXT,
    alias_normalized TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_items (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    item_date TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plan_items_plan_date
    ON plan_items (plan_id, item_date);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_thread_created
    ON assistant_messages (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assistant_runs_thread_created
    ON assistant_runs (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assistant_evidence_bundles_thread_created
    ON assistant_evidence_bundles (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assistant_memory_records_kind_created
    ON assistant_memory_records (kind, created_at);
"""


def init_assistant_schema(con: sqlite3.Connection) -> None:
    """Create assistant-owned tables and indexes using a caller-managed connection."""
    con.executescript(_SCHEMA)
