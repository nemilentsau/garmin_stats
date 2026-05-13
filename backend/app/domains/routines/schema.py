"""SQLite schema for live routine runtime storage.

Routine storage owns card templates, routine schedules, dated assignments, logs,
and overrides. These tables are created together because Today, Schedule, and
activation flows rely on their indexes as one runtime surface.
"""

from __future__ import annotations

import sqlite3

_JSON_COLS = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS card_templates ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routine_schedules ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routine_assignments (
    id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL,
    card_template_id TEXT NOT NULL,
    assignment_date TEXT NOT NULL,
    slot TEXT NOT NULL,
    position INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_logs (
    id TEXT PRIMARY KEY,
    occurrence_key TEXT NOT NULL,
    log_date TEXT NOT NULL,
    card_template_id TEXT NOT NULL,
    assignment_id TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_overrides (
    id TEXT PRIMARY KEY,
    override_date TEXT NOT NULL,
    action TEXT NOT NULL,
    target_occurrence_key TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_routine_assignments_routine_date
    ON routine_assignments (routine_id, assignment_date, slot, position);
CREATE INDEX IF NOT EXISTS idx_card_logs_date_occurrence
    ON card_logs (log_date, occurrence_key);
CREATE INDEX IF NOT EXISTS idx_card_overrides_date_action
    ON card_overrides (override_date, action);
"""


def init_routine_schema(con: sqlite3.Connection) -> None:
    """Create routine-owned tables and indexes using a caller-managed connection."""
    con.executescript(_SCHEMA)
