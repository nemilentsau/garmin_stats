"""
SQLite persistence layer for Garmin Stats.

Ingest adapters write Garmin health records into SQLite.
Read path helpers reconstruct persisted Pydantic models for API/domain adapters.
"""

import re
import sqlite3

from ..core.config import get_app_config
from ..core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    Goal,
    UserProfile,
)
from ..domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
)
from ..domains.assistant.contracts import (
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    ContextSnapshot,
    EvidenceCard,
    Plan,
    PlanItem,
)
from ..domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
    ExperimentReport,
)
from ..domains.journal.contracts import DailyCheckIn, Note
from ..domains.programs.contracts import Program, ProgramVersion
from ..utils.timeutil import now_iso
from . import cache
from .jsonstore import JsonStore
from .jsonstore import model_from_row as _model_from_row
from .sqlite import DB_PATH, connect

_APP_CONFIG = get_app_config()

DATA_DIR = _APP_CONFIG.data_dir

_ALIAS_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_VALID_TABLES = frozenset({
    "wellness_data", "sleep_data", "hrv_data",
    "skin_temp_data", "daily_metrics", "ingest_meta",
    "user_profile", "goals",
    "daily_checkins", "notes", "experiments", "experiment_exposures",
    "experiment_reports", "plans", "plan_items", "assistant_threads",
    "assistant_messages", "assistant_runs", "context_snapshots",
    "assistant_evidence_bundles", "assistant_memory_records",
    "evidence_cards", "programs", "program_versions",
    "assistant_artifacts",
})


# ---------------------------------------------------------------------------
# Schema & connection
# ---------------------------------------------------------------------------

_COLS_3 = "date TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL"
_JSON_COLS = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS wellness_data  ({_COLS_3});
CREATE TABLE IF NOT EXISTS sleep_data     ({_COLS_3});
CREATE TABLE IF NOT EXISTS hrv_data       ({_COLS_3});
CREATE TABLE IF NOT EXISTS skin_temp_data ({_COLS_3});
CREATE TABLE IF NOT EXISTS daily_metrics  ({_COLS_3});
CREATE TABLE IF NOT EXISTS ingest_meta    (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_profile   ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS goals          ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS experiments    ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS plans          ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_threads ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS context_snapshots ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS evidence_cards ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS assistant_artifacts ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS card_templates ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS routine_schedules ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS daily_checkins (
    id TEXT PRIMARY KEY,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_exposures (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_reports (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_daily_checkins_entry_date
    ON daily_checkins (entry_date);
CREATE INDEX IF NOT EXISTS idx_notes_entry_date
    ON notes (entry_date);
CREATE INDEX IF NOT EXISTS idx_experiment_exposures_experiment_date
    ON experiment_exposures (experiment_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_experiment_reports_experiment_date
    ON experiment_reports (experiment_id, report_date);
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
CREATE TABLE IF NOT EXISTS experiment_analyses (
    experiment_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS programs ({_JSON_COLS});
CREATE TABLE IF NOT EXISTS program_versions (
    program_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (program_id, version)
);
"""


def _connect():
    """Yield a sqlite3 connection with Row factory; close on exit."""
    return connect(str(DB_PATH))


def init_db() -> None:
    """Create tables if they don't exist. Enable WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as con:
        con.executescript(_SCHEMA)
        _ensure_assistant_memory_alias_lookup_columns(con)
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()


def _ensure_assistant_memory_alias_lookup_columns(con: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in con.execute("PRAGMA table_info(assistant_memory_records)").fetchall()
    }
    if "alias_normalized" not in columns:
        con.execute("ALTER TABLE assistant_memory_records ADD COLUMN alias_normalized TEXT")

    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_assistant_memory_records_kind_alias_normalized_created "
        "ON assistant_memory_records (kind, alias_normalized, created_at)"
    )

    rows = con.execute(
        "SELECT id, alias_text FROM assistant_memory_records "
        "WHERE alias_text IS NOT NULL AND (alias_normalized IS NULL OR alias_normalized = '')"
    ).fetchall()
    for row in rows:
        con.execute(
            "UPDATE assistant_memory_records SET alias_normalized = ? WHERE id = ?",
            (_normalize_alias_text(row["alias_text"]), row["id"]),
        )


def _normalize_alias_text(value: str | None) -> str | None:
    if value is None:
        return None
    tokens = _ALIAS_TOKEN_PATTERN.findall(value.lower())
    if not tokens:
        return None
    return " ".join(tokens)


_STORE = JsonStore(_VALID_TABLES)


def load_available_days() -> list[str]:
    """Load all dates that have data in the DB (cached until next ingest)."""
    return cache.cached(cache.AVAILABLE_DAYS, _fetch_available_days)


def _fetch_available_days() -> list[str]:
    with _connect() as con:
        rows = con.execute(
            "SELECT date FROM daily_metrics ORDER BY date"
        ).fetchall()
    return [r["date"] for r in rows]


# ---------------------------------------------------------------------------
# Health assistant foundation storage
# ---------------------------------------------------------------------------

def save_user_profile(profile: UserProfile) -> None:
    _STORE.save("user_profile", profile.id, profile.model_dump_json())


def load_user_profile(profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
    return _STORE.load("user_profile", UserProfile, profile_id)


def save_goal(goal: Goal) -> None:
    _STORE.save("goals", goal.id, goal.model_dump_json())


def load_goals() -> list[Goal]:
    return _STORE.load_many("goals", Goal)


def save_daily_checkin(checkin: DailyCheckIn) -> None:
    _STORE.save(
        "daily_checkins",
        checkin.id,
        checkin.model_dump_json(),
        extra_columns={"entry_date": checkin.date},
    )


def load_daily_checkins(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[DailyCheckIn]:
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _STORE.load_many(
        "daily_checkins",
        DailyCheckIn,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, id",
        last_n=last_n,
    )


def save_note(note: Note) -> None:
    _STORE.save(
        "notes",
        note.id,
        note.model_dump_json(),
        extra_columns={"entry_date": note.date},
    )


def load_notes(
    date: str | None = None,
    *,
    last_n: int | None = None,
) -> list[Note]:
    where_sql = "entry_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _STORE.load_many(
        "notes",
        Note,
        where_sql=where_sql,
        params=params,
        order_by="entry_date, created_at, id",
        last_n=last_n,
    )


def experiment_exists(experiment_id: str) -> bool:
    return _STORE.exists("experiments", experiment_id)


def load_experiment(experiment_id: str) -> Experiment | None:
    return _STORE.load("experiments", Experiment, experiment_id)


def save_experiment(experiment: Experiment) -> None:
    _STORE.save("experiments", experiment.id, experiment.model_dump_json())


def delete_experiment(experiment_id: str) -> None:
    _STORE.delete("experiments", experiment_id)


def load_experiments(
    *,
    statuses: tuple[str, ...] | None = None,
) -> list[Experiment]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if statuses is not None:
        placeholders = ", ".join("?" for _ in statuses)
        where_sql = f"json_extract(data, '$.status') IN ({placeholders})"
        params = statuses
    return _STORE.load_many("experiments", Experiment, where_sql=where_sql, params=params)


def save_experiment_exposure(exposure: ExperimentExposure) -> None:
    _STORE.save(
        "experiment_exposures",
        exposure.id,
        exposure.model_dump_json(),
        extra_columns={
            "experiment_id": exposure.experiment_id,
            "entry_date": exposure.date,
        },
    )


def replace_experiment_exposure_for_date(
    experiment_id: str,
    date: str,
    exposure: ExperimentExposure | None,
) -> None:
    """Replace the derived exposure row for one experiment-day.

    Manual same-day exposure rows are preserved and take precedence over any
    derived exposure the sync service would otherwise write.
    """
    auto_id = ExperimentExposure.auto_id(experiment_id, date)
    if exposure is not None and (
        exposure.experiment_id != experiment_id
        or exposure.date != date
        or exposure.id != auto_id
    ):
        raise ValueError("Exposure does not match experiment_id/date replacement target")

    with _connect() as con, con:
        manual_exists = con.execute(
            """
            SELECT 1
            FROM experiment_exposures
            WHERE experiment_id = ? AND entry_date = ? AND id != ?
            LIMIT 1
            """,
            (experiment_id, date, auto_id),
        ).fetchone() is not None
        con.execute("DELETE FROM experiment_exposures WHERE id = ?", (auto_id,))
        if exposure is None or manual_exists:
            return
        _STORE.save_in_connection(
            con,
            "experiment_exposures",
            exposure.id,
            exposure.model_dump_json(),
            extra_columns={
                "experiment_id": exposure.experiment_id,
                "entry_date": exposure.date,
            },
        )


def load_experiment_exposures(
    experiment_id: str | None = None,
    date: str | None = None,
) -> list[ExperimentExposure]:
    clauses: list[str] = []
    params: list[object] = []
    if experiment_id is not None:
        clauses.append("experiment_id = ?")
        params.append(experiment_id)
    if date is not None:
        clauses.append("entry_date = ?")
        params.append(date)
    return _STORE.load_many(
        "experiment_exposures",
        ExperimentExposure,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="entry_date, created_at, id",
    )


def save_experiment_report(report: ExperimentReport) -> None:
    _STORE.save(
        "experiment_reports",
        report.id,
        report.model_dump_json(),
        extra_columns={
            "experiment_id": report.experiment_id,
            "report_date": report.report_date,
        },
    )


def load_experiment_reports(experiment_id: str | None = None) -> list[ExperimentReport]:
    where_sql = "experiment_id = ?" if experiment_id is not None else ""
    params = (experiment_id,) if experiment_id is not None else ()
    return _STORE.load_many(
        "experiment_reports",
        ExperimentReport,
        where_sql=where_sql,
        params=params,
        order_by="report_date, created_at, id",
    )


def save_experiment_analysis(experiment_id: str, analysis: ExperimentAnalysis) -> None:
    """Upsert computed analysis for an experiment (keyed by experiment_id)."""
    now = now_iso()
    data_json = analysis.model_dump_json()
    with _connect() as con, con:
        con.execute(
            "INSERT OR REPLACE INTO experiment_analyses "
            "(experiment_id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (experiment_id, data_json, now, now),
        )


def delete_experiment_analysis(experiment_id: str) -> None:
    """Delete any persisted analysis for an experiment."""
    with _connect() as con, con:
        con.execute(
            "DELETE FROM experiment_analyses WHERE experiment_id = ?",
            (experiment_id,),
        )


def load_experiment_analysis(experiment_id: str) -> ExperimentAnalysis | None:
    """Load the latest computed analysis for an experiment."""
    with _connect() as con:
        row = con.execute(
            "SELECT data FROM experiment_analyses WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    if row is None:
        return None
    return ExperimentAnalysis.model_validate_json(row["data"])


def load_all_experiment_analyses() -> dict[str, ExperimentAnalysis]:
    """Load all experiment analyses, keyed by experiment_id."""
    with _connect() as con:
        rows = con.execute("SELECT experiment_id, data FROM experiment_analyses").fetchall()
    return {
        row["experiment_id"]: ExperimentAnalysis.model_validate_json(row["data"])
        for row in rows
    }


def save_plan(plan: Plan) -> None:
    _STORE.save("plans", plan.id, plan.model_dump_json())


def load_plans() -> list[Plan]:
    return _STORE.load_many("plans", Plan)


def save_plan_item(item: PlanItem) -> None:
    _STORE.save(
        "plan_items",
        item.id,
        item.model_dump_json(),
        extra_columns={
            "plan_id": item.plan_id,
            "item_date": item.date,
        },
    )


def load_plan_items(plan_id: str | None = None) -> list[PlanItem]:
    where_sql = "plan_id = ?" if plan_id is not None else ""
    params = (plan_id,) if plan_id is not None else ()
    return _STORE.load_many(
        "plan_items",
        PlanItem,
        where_sql=where_sql,
        params=params,
        order_by="item_date, created_at, id",
    )


def create_assistant_thread(thread: AssistantThread) -> None:
    created_at = thread.created_at or now_iso()
    payload = thread.model_copy(update={"created_at": created_at}).model_dump_json()
    with _connect() as con, con:
        try:
            con.execute(
                (
                    "INSERT INTO assistant_threads "
                    "(id, data, created_at, updated_at) VALUES (?, ?, ?, ?)"
                ),
                (thread.id, payload, created_at, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Assistant thread {thread.id} already exists") from exc


def save_assistant_thread(thread: AssistantThread) -> None:
    _STORE.save("assistant_threads", thread.id, thread.model_dump_json())


def load_assistant_thread(thread_id: str) -> AssistantThread | None:
    return _STORE.load("assistant_threads", AssistantThread, thread_id)


def load_assistant_threads() -> list[AssistantThread]:
    return _STORE.load_many("assistant_threads", AssistantThread)


def save_assistant_message(message: AssistantMessage) -> None:
    _STORE.save(
        "assistant_messages",
        message.id,
        message.model_dump_json(),
        extra_columns={"thread_id": message.thread_id},
        created_at=message.created_at,
    )


def load_assistant_messages(thread_id: str) -> list[AssistantMessage]:
    return _STORE.load_many(
        "assistant_messages",
        AssistantMessage,
        where_sql="thread_id = ?",
        params=(thread_id,),
        order_by="created_at, id",
    )


def save_assistant_run(run: AssistantRun) -> None:
    _STORE.save(
        "assistant_runs",
        run.id,
        run.model_dump_json(),
        extra_columns={"thread_id": run.thread_id},
        created_at=run.started_at,
        updated_at=run.finished_at or run.started_at,
    )


def finalize_assistant_reply(
    *,
    assistant_message: AssistantMessage,
    updated_thread: AssistantThread,
    completed_run: AssistantRun,
    memory_record: AssistantMemoryRecord | None = None,
) -> None:
    """Persist assistant reply + thread metadata + completed run atomically."""
    with _connect() as con, con:
        _STORE.save_in_connection(
            con,
            "assistant_messages",
            assistant_message.id,
            assistant_message.model_dump_json(),
            extra_columns={"thread_id": assistant_message.thread_id},
            created_at=assistant_message.created_at,
        )
        _STORE.save_in_connection(
            con,
            "assistant_threads",
            updated_thread.id,
            updated_thread.model_dump_json(),
        )
        _STORE.save_in_connection(
            con,
            "assistant_runs",
            completed_run.id,
            completed_run.model_dump_json(),
            extra_columns={"thread_id": completed_run.thread_id},
            created_at=completed_run.started_at,
            updated_at=completed_run.finished_at or completed_run.started_at,
        )
        if memory_record is not None:
            _STORE.save_in_connection(
                con,
                "assistant_memory_records",
                memory_record.id,
                memory_record.model_dump_json(),
                extra_columns={
                    "kind": memory_record.kind,
                    "entity_id": memory_record.entity_id,
                    "alias_text": memory_record.alias_text,
                    "alias_normalized": _normalize_alias_text(memory_record.alias_text),
                },
                created_at=memory_record.created_at,
                updated_at=memory_record.updated_at or memory_record.created_at,
            )


def load_assistant_runs(thread_id: str | None = None) -> list[AssistantRun]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _STORE.load_many(
        "assistant_runs",
        AssistantRun,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
    )


def save_assistant_evidence_bundle(bundle: AssistantEvidenceBundle) -> None:
    _STORE.save(
        "assistant_evidence_bundles",
        bundle.id,
        bundle.model_dump_json(),
        extra_columns={
            "thread_id": bundle.thread_id,
            "user_message_id": bundle.user_message_id,
            "intent": bundle.intent,
        },
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
    )


def load_assistant_evidence_bundles(
    thread_id: str | None = None,
    *,
    last_n: int | None = None,
) -> list[AssistantEvidenceBundle]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _STORE.load_many(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
        last_n=last_n,
    )


def save_assistant_memory_record(record: AssistantMemoryRecord) -> None:
    _STORE.save(
        "assistant_memory_records",
        record.id,
        record.model_dump_json(),
        extra_columns={
            "kind": record.kind,
            "entity_id": record.entity_id,
            "alias_text": record.alias_text,
            "alias_normalized": _normalize_alias_text(record.alias_text),
        },
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def load_assistant_memory_records(
    kind: str | None = None,
    *,
    last_n: int | None = None,
    alias_candidates: tuple[str, ...] | None = None,
) -> list[AssistantMemoryRecord]:
    clauses: list[str] = []
    params: list[object] = []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)

    normalized_candidates = tuple(
        normalized
        for normalized in (
            _normalize_alias_text(candidate) for candidate in (alias_candidates or ())
        )
        if normalized is not None
    )
    if alias_candidates is not None:
        if not normalized_candidates:
            return []
        placeholders = ", ".join("?" for _ in normalized_candidates)
        clauses.append(f"alias_normalized IN ({placeholders})")
        params.extend(normalized_candidates)

    return _STORE.load_many(
        "assistant_memory_records",
        AssistantMemoryRecord,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="created_at, id",
        last_n=last_n,
    )


def save_context_snapshot(snapshot: ContextSnapshot) -> None:
    _STORE.save(
        "context_snapshots",
        snapshot.id,
        snapshot.model_dump_json(),
        created_at=snapshot.created_at,
    )


def load_context_snapshot(snapshot_id: str) -> ContextSnapshot | None:
    return _STORE.load("context_snapshots", ContextSnapshot, snapshot_id)


def load_context_snapshots() -> list[ContextSnapshot]:
    return _STORE.load_many("context_snapshots", ContextSnapshot)


def save_evidence_card(card: EvidenceCard) -> None:
    _STORE.save("evidence_cards", card.id, card.model_dump_json())


def load_evidence_cards() -> list[EvidenceCard]:
    return _STORE.load_many("evidence_cards", EvidenceCard)


# ---------------------------------------------------------------------------
# Program storage
# ---------------------------------------------------------------------------


def save_program(program: Program) -> None:
    _STORE.save("programs", program.id, program.model_dump_json())


def load_program(program_id: str) -> Program | None:
    return _STORE.load("programs", Program, program_id)


def load_programs(status: str | None = None) -> list[Program]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _STORE.load_many(
        "programs",
        Program,
        where_sql=where_sql,
        params=params,
    )


def save_program_version(version: ProgramVersion) -> None:
    now = now_iso()
    data_json = version.model_dump_json()
    with _connect() as con, con:
        con.execute(
            "INSERT OR REPLACE INTO program_versions "
            "(program_id, version, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (version.program_id, version.version, data_json, now, now),
        )


def load_program_versions(program_id: str) -> list[ProgramVersion]:
    with _connect() as con:
        rows = con.execute(
            "SELECT data, created_at, updated_at FROM program_versions "
            "WHERE program_id = ? ORDER BY version",
            (program_id,),
        ).fetchall()
    return [_model_from_row(ProgramVersion, row) for row in rows]


def delete_program(program_id: str) -> None:
    with _connect() as con, con:
        con.execute("DELETE FROM programs WHERE id = ?", (program_id,))
        con.execute(
            "DELETE FROM program_versions WHERE program_id = ?",
            (program_id,),
        )


def save_program_import(
    *,
    program: Program,
    previous_version: ProgramVersion | None,
) -> None:
    """Persist a placeholder program import and optional previous version atomically."""
    timestamp = now_iso()
    with _connect() as con, con:
        if previous_version is not None:
            con.execute(
                "INSERT OR REPLACE INTO program_versions "
                "(program_id, version, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    previous_version.program_id,
                    previous_version.version,
                    previous_version.model_dump_json(),
                    timestamp,
                    timestamp,
                ),
            )

        _STORE.save_in_connection(
            con,
            "programs",
            program.id,
            program.model_dump_json(),
        )
