"""Tests for SQLite storage initialization and shared JSON persistence behavior."""

import app.domains.routines.adapters as routine_db
import app.infra.sqlite as sqlite
from app.core.profile.adapters import SqliteProfileRepository
from app.core.profile.contracts import UserProfile
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
)
from app.domains.routines.contracts import (
    CardLog,
    CardOverride,
    CardTemplate,
    MeditationTimerPayload,
    RoutineAssignment,
    RoutineSchedule,
)
from tests._routines_helpers import persist_card_override

# ---------------------------------------------------------------------------
# init & schema
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_all_required_tables(self, tmp_db):
        with sqlite.connect() as con:
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "wellness_data" in tables
        assert "daily_metrics" in tables
        assert "ingest_meta" in tables
        assert "user_profile" in tables
        assert "assistant_artifacts" in tables
        assert "card_templates" in tables
        assert "routine_schedules" in tables
        assert "routine_assignments" in tables
        assert "card_logs" in tables
        assert "card_overrides" in tables

    def test_enables_wal_journal_mode(self, tmp_db):
        with sqlite.connect() as con:
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_bootstrap_storage_is_idempotent_and_creates_domain_tables(
        self,
        tmp_path,
        monkeypatch,
    ):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "bootstrap-storage.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)

        storage_schema.init_storage()
        storage_schema.init_storage()

        with sqlite.connect() as con:
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert {
            "wellness_data",
            "ingest_meta",
            "user_profile",
            "routine_assignments",
            "experiment_exposures",
            "assistant_artifacts",
            "daily_checkins",
        }.issubset(tables)
        assert "program_versions" not in tables

    def test_bootstrap_storage_removes_retired_program_tables_from_existing_database(
        self,
        tmp_path,
        monkeypatch,
    ):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "upgraded-storage.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.execute("CREATE TABLE programs (id TEXT PRIMARY KEY)")
            con.execute("CREATE TABLE program_versions (id TEXT PRIMARY KEY)")

        storage_schema.init_storage()
        storage_schema.init_storage()

        with sqlite.connect() as con:
            tables = {
                row["name"]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "programs" not in tables
        assert "program_versions" not in tables


# ---------------------------------------------------------------------------
# Store and load round-trips
# ---------------------------------------------------------------------------

def _make_daily_metric(date: str, utc_offset_hours: float | None = None) -> DailyMetric:
    """Build a minimal DailyMetric for storage tests."""
    return DailyMetric(
        date=date,
        utc_offset_hours=utc_offset_hours,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, resting=48),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(nightly_avg=55.0, weekly_avg=52.0, status="balanced"),
        sleep=DailySleepStats(score=85),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


class TestStoreAndLoad:
    def test_user_profile_survives_round_trip(self):
        profile = UserProfile(
            name="Andrei",
            primary_goals=["better recovery"],
            nutrition_preferences=["high protein"],
        )

        repo = SqliteProfileRepository()
        repo.save_profile(profile)
        loaded = repo.get_profile()

        assert loaded is not None
        assert loaded.name == "Andrei"
        assert loaded.primary_goals == ["better recovery"]

    def test_json_record_update_preserves_created_at(self):
        repo = SqliteProfileRepository()
        repo.save_profile(UserProfile(name="Andrei"))
        with sqlite.connect() as con:
            first = con.execute(
                "SELECT created_at, updated_at FROM user_profile WHERE id = ?",
                ("default",),
            ).fetchone()

        repo.save_profile(UserProfile(name="Andrei N."))
        with sqlite.connect() as con:
            second = con.execute(
                "SELECT created_at, updated_at FROM user_profile WHERE id = ?",
                ("default",),
            ).fetchone()

        assert first is not None
        assert second is not None
        assert second["created_at"] == first["created_at"]
        assert second["updated_at"] >= first["updated_at"]

    def test_routine_runtime_records_survive_round_trip(self):
        card = CardTemplate(
            id="card-1",
            name="Open Monitoring",
            slot_default="evening",
            payload_json=MeditationTimerPayload(
                duration_minutes=15,
                technique="focused_attention",
            ),
        )
        routine = RoutineSchedule(
            id="routine-1",
            name="Mindfulness",
            start_date="2026-03-02",
        )
        assignment = RoutineAssignment(
            id="assignment-1",
            routine_id="routine-1",
            card_template_id="card-1",
            date="2026-03-02",
            slot="evening",
        )
        log = CardLog(
            id="log-1",
            date="2026-03-02",
            occurrence_key="scheduled:assignment-1:2026-03-02",
            card_template_id="card-1",
            assignment_id="assignment-1",
            status="completed",
        )
        override = CardOverride(
            id="override-1",
            date="2026-03-02",
            action="hide",
            target_occurrence_key="scheduled:assignment-1:2026-03-02",
        )

        routine_db.save_card_template(card)
        routine_db.save_routine_schedule_with_assignments(routine, [assignment])
        routine_db.save_card_log(log)
        persist_card_override(override)

        assert [entry.id for entry in routine_db.load_card_templates()] == ["card-1"]
        assert [entry.id for entry in routine_db.load_routine_schedules()] == ["routine-1"]
        assert [entry.id for entry in routine_db.load_routine_assignments("routine-1")] == [
            "assignment-1"
        ]
        assert [entry.id for entry in routine_db.load_card_logs("2026-03-02")] == ["log-1"]
        assert [
            entry.id
            for entry in routine_db.load_card_overrides_range("2026-03-02", "2026-03-02")
        ] == [
            "override-1"
        ]

# ---------------------------------------------------------------------------
# Period summary storage
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Card override range query (Task 3)
# ---------------------------------------------------------------------------

class TestCardOverridesRange:
    def test_range_query_matches_individual_date_queries(self):
        dates = ["2026-03-02", "2026-03-03", "2026-03-04"]
        for i, date in enumerate(dates):
            persist_card_override(CardOverride(
                id=f"override-{i}",
                date=date,
                action="hide",
                target_occurrence_key=f"key-{i}",
            ))

        range_result = routine_db.load_card_overrides_range("2026-03-02", "2026-03-04")
        individual_results = []
        for date in dates:
            individual_results.extend(routine_db.load_card_overrides_range(date, date))

        assert [o.id for o in range_result] == [o.id for o in individual_results]
