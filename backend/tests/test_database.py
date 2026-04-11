"""Tests for database.py — connection, storage, read-back."""

import os

import pytest

import app.infra.database as db
from app.domains.assistant.application.types import (
    AssistantEvidenceBundle,
    AssistantEvidenceItem,
    AssistantMemoryRecord,
    AssistantResolvedEntity,
)
from app.models import (
    AssistantArtifact,
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    CardLog,
    CardOverride,
    CardTemplate,
    ContextSnapshot,
    DailyBodyBatteryStats,
    DailyCheckIn,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    EvidenceCard,
    Experiment,
    ExperimentExposure,
    Goal,
    Note,
    OutcomeMetric,
    Plan,
    PlanItem,
    Routine,
    RoutineAssignment,
    RoutineEntry,
    RoutineSchedule,
    UserProfile,
)
from app.utils.timeutil import now_iso

# ---------------------------------------------------------------------------
# init & schema
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_all_required_tables(self, tmp_db):
        with db._connect() as con:
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "wellness_data" in tables
        assert "daily_metrics" in tables
        assert "ingest_meta" in tables
        assert "user_profile" in tables
        assert "routines" in tables
        assert "assistant_threads" in tables
        assert "assistant_evidence_bundles" in tables
        assert "assistant_memory_records" in tables
        assert "assistant_artifacts" in tables
        assert "card_templates" in tables
        assert "routine_schedules" in tables
        assert "routine_assignments" in tables
        assert "card_logs" in tables
        assert "card_overrides" in tables

    def test_enables_wal_journal_mode(self, tmp_db):
        with db._connect() as con:
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


# ---------------------------------------------------------------------------
# count_rows
# ---------------------------------------------------------------------------

class TestCountRows:
    def test_returns_zero_for_empty_table(self):
        assert db._count_rows("daily_metrics") == 0

    def test_rejects_invalid_table_name(self):
        with pytest.raises(ValueError, match="Invalid table name"):
            db._count_rows("users; DROP TABLE daily_metrics")


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

class TestFingerprint:
    def test_detects_file_content_change(self, tmp_path):
        data_dir = tmp_path / "data"
        day_dir = data_dir / "2026-01-15"
        day_dir.mkdir(parents=True)
        fit_file = day_dir / "001_WELLNESS.fit"
        fit_file.write_bytes(b"AAAA")
        fp1 = db.compute_data_fingerprint(data_dir)

        fit_file.write_bytes(b"BBBB")
        stat = fit_file.stat()
        os.utime(fit_file, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 1))
        fp2 = db.compute_data_fingerprint(data_dir)

        assert fp1 != fp2

    def test_returns_stable_hash_for_nonexistent_dir(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        fp = db.compute_data_fingerprint(missing)
        assert isinstance(fp, str)
        assert len(fp) == 64  # SHA-256 hex digest


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
    def test_wellness_survives_round_trip(self):
        wellness = DayWellness(date="2026-01-15")
        with db._connect() as con:
            con.execute(
                "INSERT INTO wellness_data (date, data, updated_at) VALUES (?, ?, ?)",
                ("2026-01-15", wellness.model_dump_json(), "2026-01-15T00:00:00Z"),
            )
            con.commit()
        loaded = db.load_wellness("2026-01-15")
        assert len(loaded) == 1
        assert loaded[0].date == "2026-01-15"

    def test_daily_metrics_survive_round_trip(self):
        metric = _make_daily_metric("2026-01-15")
        with db._connect() as con:
            con.execute(
                "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                ("2026-01-15", metric.model_dump_json(), "2026-01-15T00:00:00Z"),
            )
            con.commit()
        loaded = db.load_daily_metrics()
        assert len(loaded) == 1
        assert loaded[0].heart_rate.avg == 70.0
        assert loaded[0].heart_rate.resting == 48

    def test_available_days_returned_sorted(self):
        for date in ["2026-01-15", "2026-01-16", "2026-01-17"]:
            metric = _make_daily_metric(date)
            with db._connect() as con:
                con.execute(
                    "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                    (date, metric.model_dump_json(), "now"),
                )
                con.commit()
        days = db.load_available_days()
        assert days == ["2026-01-15", "2026-01-16", "2026-01-17"]

    def test_is_db_empty_true_when_no_metrics(self):
        assert db.is_db_empty() is True

    def test_is_db_empty_false_after_insert(self):
        metric = _make_daily_metric("2026-01-15")
        with db._connect() as con:
            con.execute(
                "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                ("2026-01-15", metric.model_dump_json(), "now"),
            )
            con.commit()
        assert db.is_db_empty() is False

    def test_user_profile_survives_round_trip(self):
        profile = UserProfile(
            name="Andrei",
            primary_goals=["better recovery"],
            nutrition_preferences=["high protein"],
        )

        db.save_user_profile(profile)
        loaded = db.load_user_profile()

        assert loaded is not None
        assert loaded.name == "Andrei"
        assert loaded.primary_goals == ["better recovery"]

    def test_json_record_update_preserves_created_at(self):
        db.save_goal(Goal(id="goal-1", title="Recover better"))
        with db._connect() as con:
            first = con.execute(
                "SELECT created_at, updated_at FROM goals WHERE id = ?",
                ("goal-1",),
            ).fetchone()

        db.save_goal(Goal(id="goal-1", title="Recover much better"))
        with db._connect() as con:
            second = con.execute(
                "SELECT created_at, updated_at FROM goals WHERE id = ?",
                ("goal-1",),
            ).fetchone()

        assert first is not None
        assert second is not None
        assert second["created_at"] == first["created_at"]
        assert second["updated_at"] >= first["updated_at"]

    def test_loader_hydrates_generated_timestamps_from_columns(self):
        db.save_assistant_thread(AssistantThread(id="thread-1", title="Recovery coach"))
        db.save_assistant_message(
            AssistantMessage(
                id="message-1",
                thread_id="thread-1",
                role="assistant",
                content_markdown="Sleep dipped last night.",
            )
        )
        db.save_context_snapshot(ContextSnapshot(id="snapshot-1"))

        messages = db.load_assistant_messages("thread-1")
        loaded_snapshot = db.load_context_snapshot("snapshot-1")

        assert messages[0].created_at is not None
        assert loaded_snapshot is not None
        assert loaded_snapshot.created_at is not None

    def test_routine_entries_filter_by_routine_and_date(self):
        routine = Routine(
            id="routine-1",
            name="Meditation",
            category="mindfulness",
        )
        db.save_routine(routine)

        db.save_routine_entry(
            RoutineEntry(
                id="entry-1",
                routine_id="routine-1",
                date="2026-01-15",
                value_numeric=10,
            )
        )
        db.save_routine_entry(
            RoutineEntry(
                id="entry-2",
                routine_id="routine-1",
                date="2026-01-16",
                value_numeric=5,
            )
        )
        db.save_routine_entry(
            RoutineEntry(
                id="entry-3",
                routine_id="routine-2",
                date="2026-01-15",
                value_numeric=20,
            )
        )

        loaded = db.load_routine_entries(routine_id="routine-1", date="2026-01-15")

        assert [entry.id for entry in loaded] == ["entry-1"]

    def test_daily_checkin_and_note_survive_round_trip(self):
        db.save_daily_checkin(
            DailyCheckIn(
                id="checkin-2026-01-15",
                date="2026-01-15",
                energy=4,
                notes="Felt solid",
            )
        )
        db.save_note(
            Note(
                id="note-1",
                date="2026-01-15",
                category="nutrition",
                title="Dinner",
                content="More carbs than usual",
            )
        )

        checkins = db.load_daily_checkins("2026-01-15")
        notes = db.load_notes("2026-01-15")

        assert len(checkins) == 1
        assert checkins[0].energy == 4
        assert len(notes) == 1
        assert notes[0].title == "Dinner"

    def test_experiment_family_survives_round_trip(self):
        experiment = Experiment(
            id="exp-1",
            name="Evening meditation",
            linked_routine_ids=["routine-1"],
            outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
        )
        exposure = ExperimentExposure(
            id="exposure-1",
            experiment_id="exp-1",
            date="2026-01-15",
            exposure_score=1.0,
            adherence_state="completed",
        )

        db.save_experiment(experiment)
        db.save_experiment_exposure(exposure)

        experiments = db.load_experiments()
        exposures = db.load_experiment_exposures(experiment_id="exp-1")

        assert [item.id for item in experiments] == ["exp-1"]
        assert [item.id for item in exposures] == ["exposure-1"]

    def test_plan_survives_round_trip_with_items(self):
        plan = Plan(
            id="plan-1",
            title="Recovery Week",
            scope="weekly",
            linked_experiment_ids=["exp-1"],
        )
        item = PlanItem(
            id="item-1",
            plan_id="plan-1",
            title="Meditate before bed",
            date="2026-01-15",
        )

        db.save_plan(plan)
        db.save_plan_item(item)

        plans = db.load_plans()
        items = db.load_plan_items("plan-1")

        assert [entry.id for entry in plans] == ["plan-1"]
        assert [entry.id for entry in items] == ["item-1"]

    def test_assistant_foundation_records_survive_round_trip(self):
        thread = AssistantThread(
            id="thread-1",
            title="Recovery coach",
            model="opus",
            claude_session_id="session-123",
        )
        message = AssistantMessage(
            id="message-1",
            thread_id="thread-1",
            role="assistant",
            content_markdown="Sleep dipped last night.",
            created_at="2026-01-15T08:00:00+00:00",
        )
        snapshot = ContextSnapshot(
            id="snapshot-1",
            date_window_start="2026-01-01",
            date_window_end="2026-01-15",
            summary_markdown="Last 14 days summary",
        )
        card = EvidenceCard(
            id="card-1",
            kind="trend",
            title="HRV below baseline",
            summary="Nightly HRV is down over the last 3 days.",
            confidence="moderate",
        )

        db.save_assistant_thread(thread)
        db.save_assistant_message(message)
        db.save_context_snapshot(snapshot)
        db.save_evidence_card(card)

        threads = db.load_assistant_threads()
        messages = db.load_assistant_messages("thread-1")
        loaded_snapshot = db.load_context_snapshot("snapshot-1")
        cards = db.load_evidence_cards()

        assert [entry.id for entry in threads] == ["thread-1"]
        assert [entry.id for entry in messages] == ["message-1"]
        assert loaded_snapshot is not None
        assert loaded_snapshot.id == "snapshot-1"
        assert [entry.id for entry in cards] == ["card-1"]

    def test_finalize_assistant_reply_persists_message_thread_and_run_state_together(self):
        thread = AssistantThread(
            id="thread-1",
            title="Recovery coach",
            last_message_at="2026-01-14T10:00:00+00:00",
        )
        running_run = AssistantRun(
            id="run-1",
            task_type="chat",
            status="running",
            thread_id="thread-1",
            started_at="2026-01-15T09:00:00+00:00",
        )
        assistant_message = AssistantMessage(
            id="assistant-1",
            thread_id="thread-1",
            role="assistant",
            content_markdown="Keep the bedtime routine consistent.",
            created_at="2026-01-15T09:02:00+00:00",
        )
        updated_thread = thread.model_copy(
            update={
                "claude_session_id": "session-1",
                "last_context_snapshot_id": "bundle-1",
                "last_message_at": assistant_message.created_at,
            }
        )
        completed_run = running_run.model_copy(
            update={
                "status": "completed",
                "context_snapshot_id": "bundle-1",
                "claude_session_id": "session-1",
                "finished_at": "2026-01-15T09:02:01+00:00",
            }
        )

        db.create_assistant_thread(thread)
        db.save_assistant_run(running_run)
        assert db.load_assistant_messages("thread-1") == []
        assert db.load_assistant_runs("thread-1")[0].status == "running"

        db.finalize_assistant_reply(
            assistant_message=assistant_message,
            updated_thread=updated_thread,
            completed_run=completed_run,
        )

        loaded_thread = db.load_assistant_thread("thread-1")
        loaded_messages = db.load_assistant_messages("thread-1")
        loaded_runs = db.load_assistant_runs("thread-1")

        assert loaded_thread is not None
        assert loaded_thread.last_message_at == assistant_message.created_at
        assert loaded_thread.last_context_snapshot_id == "bundle-1"
        assert loaded_thread.claude_session_id == "session-1"
        assert [message.id for message in loaded_messages] == ["assistant-1"]
        assert loaded_runs[0].id == "run-1"
        assert loaded_runs[0].status == "completed"
        assert loaded_runs[0].finished_at == "2026-01-15T09:02:01+00:00"
        assert loaded_runs[0].context_snapshot_id == "bundle-1"

    def test_missing_context_snapshot_returns_none(self):
        assert db.load_context_snapshot("missing") is None

    def test_training_runtime_records_survive_round_trip(self):
        artifact = AssistantArtifact(
            id="artifact-1",
            kind="card_template",
            schema_version=1,
            status="validated",
            payload_json={"id": "card-1"},
        )
        card = CardTemplate(
            id="card-1",
            name="Open Monitoring",
            renderer="timer_session",
            slot_default="evening",
            payload_json={"duration_minutes": 15},
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

        db.save_assistant_artifact(artifact)
        db.save_card_template(card)
        db.save_routine_schedule(routine)
        db.save_routine_assignment(assignment)
        db.save_card_log(log)
        db.save_card_override(override)

        assert db.load_assistant_artifact("artifact-1") is not None
        assert [entry.id for entry in db.load_card_templates()] == ["card-1"]
        assert [entry.id for entry in db.load_routine_schedules()] == ["routine-1"]
        assert [entry.id for entry in db.load_routine_assignments("routine-1")] == ["assignment-1"]
        assert [entry.id for entry in db.load_card_logs("2026-03-02")] == ["log-1"]
        assert [entry.id for entry in db.load_card_overrides("2026-03-02")] == ["override-1"]

    def test_assistant_evidence_bundle_round_trips(self):
        bundle = AssistantEvidenceBundle(
            id="bundle-1",
            thread_id="thread-1",
            user_message_id="message-1",
            intent="experiment_review",
            entities=[
                AssistantResolvedEntity(
                    kind="experiment",
                    entity_id="exp-1",
                    label="Meditation → HRV",
                    score=0.98,
                )
            ],
            items=[
                AssistantEvidenceItem(
                    kind="analysis",
                    source="experiment_analysis",
                    entity_id="exp-1",
                    payload_json={"adherence_rate": 0.5},
                )
            ],
        )

        db.save_assistant_evidence_bundle(bundle)
        loaded = db.load_assistant_evidence_bundles(thread_id="thread-1")

        assert loaded[0].intent == "experiment_review"
        assert loaded[0].entities[0].entity_id == "exp-1"

    def test_assistant_memory_record_round_trips(self):
        record = AssistantMemoryRecord(
            id="memory-1",
            kind="entity_alias",
            entity_id="exp-1",
            alias_text="meditation experiment",
            payload_json={"source": "resolver"},
        )

        db.save_assistant_memory_record(record)
        loaded = db.load_assistant_memory_records(kind="entity_alias")

        assert loaded[0].alias_text == "meditation experiment"


# ---------------------------------------------------------------------------
# Period summary storage
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# _delete_stale_day_rows
# ---------------------------------------------------------------------------

class TestDeleteStaleRows:
    def test_removes_dates_absent_from_parsed_input(self):
        date_keep = "2026-01-15"
        date_drop = "2026-01-16"
        now = "2026-01-15T00:00:00Z"

        tables = [
            (
                "wellness_data",
                DayWellness(date=date_keep).model_dump_json(),
                DayWellness(date=date_drop).model_dump_json(),
            ),
            (
                "sleep_data",
                DaySleep(date=date_keep).model_dump_json(),
                DaySleep(date=date_drop).model_dump_json(),
            ),
            (
                "hrv_data",
                DayHrv(date=date_keep).model_dump_json(),
                DayHrv(date=date_drop).model_dump_json(),
            ),
            (
                "skin_temp_data",
                DaySkinTemp(date=date_keep).model_dump_json(),
                DaySkinTemp(date=date_drop).model_dump_json(),
            ),
            (
                "daily_metrics",
                _make_daily_metric(date_keep).model_dump_json(),
                _make_daily_metric(date_drop).model_dump_json(),
            ),
        ]

        with db._connect() as con:
            for table, keep_payload, drop_payload in tables:
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    (date_keep, keep_payload, now),
                )
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    (date_drop, drop_payload, now),
                )
            con.commit()

            db._delete_stale_day_rows(con, [date_keep])
            con.commit()

            for table, _, _ in tables:
                rows = con.execute(f"SELECT date FROM {table} ORDER BY date").fetchall()
                assert [r["date"] for r in rows] == [date_keep]

    def test_empty_parsed_dates_deletes_all_rows(self):
        """When no dates are parsed, all per-day rows should be deleted."""
        now = "2026-01-15T00:00:00Z"
        tables = (
            "wellness_data", "sleep_data", "hrv_data",
            "skin_temp_data", "daily_metrics",
        )
        with db._connect() as con:
            for table in tables:
                con.execute(
                    f"INSERT INTO {table} (date, data, updated_at) VALUES (?, ?, ?)",
                    ("2026-01-15", "{}", now),
                )
            con.commit()

            db._delete_stale_day_rows(con, [])
            con.commit()

            for table in tables:
                count = con.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table}"
                ).fetchone()["cnt"]
                assert count == 0


# ---------------------------------------------------------------------------
# Card override range query (Task 3)
# ---------------------------------------------------------------------------

class TestCardOverridesRange:
    def test_range_query_matches_individual_date_queries(self):
        dates = ["2026-03-02", "2026-03-03", "2026-03-04"]
        for i, date in enumerate(dates):
            db.save_card_override(CardOverride(
                id=f"override-{i}",
                date=date,
                action="hide",
                target_occurrence_key=f"key-{i}",
            ))

        range_result = db.load_card_overrides_range("2026-03-02", "2026-03-04")
        individual_results = []
        for date in dates:
            individual_results.extend(db.load_card_overrides(date=date))

        assert [o.id for o in range_result] == [o.id for o in individual_results]


# ---------------------------------------------------------------------------
# Targeted artifact DB queries (Task 4)
# ---------------------------------------------------------------------------

class TestArtifactQueryFunctions:
    def test_load_artifact_by_payload_id_finds_matching_artifact(self):
        now = now_iso()
        artifact = AssistantArtifact(
            id="bundle:test-bundle:card_template:card-1:r1",
            kind="card_template",
            schema_version=1,
            status="validated",
            payload_json={"id": "card-1", "name": "Test"},
            created_at=now,
            updated_at=now,
        )
        db.save_assistant_artifact(artifact)

        result = db.load_assistant_artifact_by_payload_id(
            "card_template", "card-1", ("validated", "activated"),
        )

        assert result is not None
        assert result.id == artifact.id

    def test_load_max_artifact_revision_returns_highest(self):
        now = now_iso()
        prefix = "bundle:test:card_template:card-1:r"
        for rev in [1, 2, 5]:
            db.save_assistant_artifact(AssistantArtifact(
                id=f"{prefix}{rev}",
                kind="card_template",
                schema_version=1,
                status="validated",
                payload_json={"id": "card-1"},
                created_at=now,
                updated_at=now,
            ))

        result = db.load_max_artifact_revision("card_template", prefix)

        assert result == 5


# ---------------------------------------------------------------------------
# last_n query parameter (Task 5)
# ---------------------------------------------------------------------------

class TestLastNQuery:
    def test_last_n_returns_correct_tail_in_ascending_order(self):
        for i in range(10):
            date = f"2026-03-{i + 1:02d}"
            db.save_daily_checkin(DailyCheckIn(id=f"checkin-{i}", date=date))

        result = db.load_daily_checkins(last_n=3)

        assert len(result) == 3
        assert result[0].date == "2026-03-08"
        assert result[1].date == "2026-03-09"
        assert result[2].date == "2026-03-10"


# ---------------------------------------------------------------------------
# Auto-total response model (Task 2)
# ---------------------------------------------------------------------------

class TestAutoTotal:
    def test_auto_total_computed_from_items(self):
        from app.models import GoalsResponse

        response = GoalsResponse(goals=[Goal(id="g1", title="Recovery")])

        assert response.total == 1

    def test_explicit_total_is_respected(self):
        from app.models import GoalsResponse

        response = GoalsResponse(goals=[Goal(id="g1", title="Recovery")], total=42)

        assert response.total == 42
