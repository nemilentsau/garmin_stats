"""Tests for SQLite storage initialization and shared JSON persistence behavior."""

import json

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
        assert "training_blocks" in tables
        assert "training_bundles" in tables
        assert "training_card_logs" in tables

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
            "experiment_exposures",
            "daily_checkins",
        }.issubset(tables)
        assert "program_versions" not in tables

    def test_bootstrap_storage_removes_retired_product_tables_from_existing_database(
        self,
        tmp_path,
        monkeypatch,
    ):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "upgraded-storage.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            for table in storage_schema._RETIRED_TABLES:
                con.execute(f'CREATE TABLE "{table}" (id TEXT PRIMARY KEY)')

        storage_schema.init_storage()
        storage_schema.init_storage()

        with sqlite.connect() as con:
            tables = {
                row["name"]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert set(storage_schema._RETIRED_TABLES).isdisjoint(tables)

    def test_bootstrap_storage_retires_derived_exposures_and_deduplicates_manual_days(
        self,
        tmp_path,
        monkeypatch,
    ):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "exposure-upgrade.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.executescript(
                """
                CREATE TABLE experiment_exposures (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE experiment_analyses (
                    experiment_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            con.executemany(
                "INSERT INTO experiment_exposures VALUES (?, ?, ?, '{}', ?, ?)",
                [
                    (
                        "exposure:auto:auto-exp:2026-01-01",
                        "auto-exp",
                        "2026-01-01",
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    ),
                    (
                        "manual-old",
                        "manual-exp",
                        "2026-01-02",
                        "2026-01-02T00:00:00Z",
                        "2026-01-02T01:00:00Z",
                    ),
                    (
                        "manual-new",
                        "manual-exp",
                        "2026-01-02",
                        "2026-01-02T00:00:00Z",
                        "2026-01-02T02:00:00Z",
                    ),
                ],
            )
            con.executemany(
                "INSERT INTO experiment_analyses VALUES (?, '{}', ?, ?)",
                [
                    ("auto-exp", "2026-01-03T00:00:00Z", "2026-01-03T00:00:00Z"),
                    ("manual-exp", "2026-01-03T00:00:00Z", "2026-01-03T00:00:00Z"),
                    ("untouched-exp", "2026-01-03T00:00:00Z", "2026-01-03T00:00:00Z"),
                ],
            )
            con.commit()

        storage_schema.init_storage()
        storage_schema.init_storage()

        with sqlite.connect() as con:
            exposure_ids = [
                row["id"]
                for row in con.execute(
                    "SELECT id FROM experiment_exposures ORDER BY id"
                ).fetchall()
            ]
            analysis_ids = [
                row["experiment_id"]
                for row in con.execute(
                    "SELECT experiment_id FROM experiment_analyses ORDER BY experiment_id"
                ).fetchall()
            ]
            unique_indexes = [
                row["name"]
                for row in con.execute("PRAGMA index_list('experiment_exposures')")
                if row["unique"] == 1
            ]

        assert exposure_ids == ["manual-new"]
        assert analysis_ids == ["untouched-exp"]
        assert "uq_experiment_exposures_experiment_date" in unique_indexes

    def test_bootstrap_namespaces_legacy_coach_occurrences_once(self, tmp_db):
        from app.bootstrap import schema as storage_schema
        from app.domains.training.domain.instance_identity import (
            program_instance_id,
        )

        instance_id = program_instance_id(
            block={"block_id": "block-1"},
            bundles=[],
            registry={},
            library={},
            schedule_start="2026-01-01",
        )
        legacy_key = "run:measurement:d01"
        durable_key = f"{instance_id}:{legacy_key}"
        with sqlite.connect() as con:
            con.execute(
                "INSERT INTO training_blocks (id, data, created_at, updated_at) "
                "VALUES ('block-1', ?, 'now', 'now')",
                (json.dumps({"status": "active", "program_instance_id": instance_id}),),
            )
            review = {
                "occurrence_key": legacy_key,
                "measurement_assessment": {"occurrence_key": legacy_key},
            }
            con.execute(
                "INSERT INTO coach_reviews "
                "(id, date, kind, run_id, occurrence_key, status, updated_at, data) "
                "VALUES ('review-1', '2026-01-01', 'run', 'run-1', ?, "
                "'complete', 'now', ?)",
                (legacy_key, json.dumps(review)),
            )
            con.execute(
                "INSERT INTO coach_review_revisions "
                "(id, review_id, version, created_at, data) "
                "VALUES ('revision-1', 'review-1', 1, 'now', ?)",
                (json.dumps(review),),
            )
            con.execute(
                "INSERT INTO coach_messages (id, thread_id, created_at, data) "
                "VALUES ('message-1', 'thread-1', 'now', ?)",
                (json.dumps({"measurement_assessment": {"occurrence_key": legacy_key}}),),
            )
            con.execute(
                "INSERT INTO coach_jobs "
                "(id, kind, dedupe_key, priority, status, available_at, created_at, "
                "updated_at, data) VALUES "
                "('job-1', 'review_run', 'review:run:run-1', 1, 'complete', "
                "'now', 'now', 'now', ?)",
                (json.dumps({"payload": {"occurrence_key": legacy_key}}),),
            )

            con.commit()

        storage_schema.init_storage()
        storage_schema.init_storage()

        with sqlite.connect() as con:

            stored_review = con.execute(
                "SELECT occurrence_key, data FROM coach_reviews WHERE id = 'review-1'"
            ).fetchone()
            stored_revision = con.execute(
                "SELECT data FROM coach_review_revisions WHERE id = 'revision-1'"
            ).fetchone()
            stored_message = con.execute(
                "SELECT data FROM coach_messages WHERE id = 'message-1'"
            ).fetchone()
            stored_job = con.execute(
                "SELECT data FROM coach_jobs WHERE id = 'job-1'"
            ).fetchone()

        assert stored_review["occurrence_key"] == durable_key
        assert json.loads(stored_review["data"])["measurement_assessment"][
            "occurrence_key"
        ] == durable_key
        assert json.loads(stored_revision["data"])["occurrence_key"] == durable_key
        assert json.loads(stored_message["data"])["measurement_assessment"][
            "occurrence_key"
        ] == durable_key
        assert json.loads(stored_job["data"])["payload"]["occurrence_key"] == durable_key


class TestPreMigrationBackup:
    def test_destructive_migration_backs_up_database_first(self, tmp_path, monkeypatch):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-storage.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.execute('CREATE TABLE "card_logs" (id TEXT PRIMARY KEY)')
            con.execute("INSERT INTO card_logs VALUES ('card-1')")
            con.commit()

        storage_schema.init_storage()

        backup_dir = test_db.parent / "backups"
        backups = list(backup_dir.glob("pre-migration-*.db"))
        assert len(backups) == 1

        with sqlite.connect(str(backups[0])) as con:
            backed_up_ids = [row["id"] for row in con.execute("SELECT id FROM card_logs")]
        assert backed_up_ids == ["card-1"]

        with sqlite.connect() as con:
            tables = {
                row["name"]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "card_logs" not in tables

    def test_second_init_run_is_noop_and_creates_no_new_backup(self, tmp_path, monkeypatch):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-noop.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.execute('CREATE TABLE "card_logs" (id TEXT PRIMARY KEY)')
            con.execute("INSERT INTO card_logs VALUES ('card-1')")
            con.commit()

        storage_schema.init_storage()
        storage_schema.init_storage()

        backup_dir = test_db.parent / "backups"
        backups = list(backup_dir.glob("pre-migration-*.db"))
        assert len(backups) == 1

    def test_clean_database_never_creates_backup(self, tmp_path, monkeypatch):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-clean.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)

        storage_schema.init_storage()

        backup_dir = test_db.parent / "backups"
        assert not backup_dir.exists() or not list(backup_dir.glob("pre-migration-*.db"))

    def test_empty_retired_table_never_creates_backup(self, tmp_path, monkeypatch):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-empty-retired.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.execute('CREATE TABLE "card_logs" (id TEXT PRIMARY KEY)')
            con.commit()

        storage_schema.init_storage()

        backup_dir = test_db.parent / "backups"
        assert not backup_dir.exists() or not list(backup_dir.glob("pre-migration-*.db"))

    def test_auto_exposure_purge_triggers_backup(self, tmp_path, monkeypatch):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-auto-exposure.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.executescript(
                """
                CREATE TABLE experiment_exposures (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "INSERT INTO experiment_exposures VALUES "
                "('exposure:auto:auto-exp:2026-01-01', 'auto-exp', '2026-01-01', "
                "'{}', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
            con.commit()

        storage_schema.init_storage()

        backup_dir = test_db.parent / "backups"
        backups = list(backup_dir.glob("pre-migration-*.db"))
        assert len(backups) == 1

    def test_duplicate_manual_exposures_trigger_backup(self, tmp_path, monkeypatch):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-duplicate-manual.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        with sqlite.connect() as con:
            con.executescript(
                """
                CREATE TABLE experiment_exposures (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "INSERT INTO experiment_exposures VALUES "
                "('exposure:manual:dup-exp:2026-01-01:a', 'dup-exp', '2026-01-01', "
                "'{}', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
            con.execute(
                "INSERT INTO experiment_exposures VALUES "
                "('exposure:manual:dup-exp:2026-01-01:b', 'dup-exp', '2026-01-01', "
                "'{}', '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')"
            )
            con.commit()

        storage_schema.init_storage()

        backup_dir = test_db.parent / "backups"
        backups = list(backup_dir.glob("pre-migration-*.db"))
        assert len(backups) == 1

        with sqlite.connect(str(backups[0])) as con:
            backed_up_ids = {
                row["id"] for row in con.execute("SELECT id FROM experiment_exposures")
            }
        assert backed_up_ids == {
            "exposure:manual:dup-exp:2026-01-01:a",
            "exposure:manual:dup-exp:2026-01-01:b",
        }

        with sqlite.connect() as con:
            live_ids = [
                row["id"] for row in con.execute("SELECT id FROM experiment_exposures")
            ]
        assert live_ids == ["exposure:manual:dup-exp:2026-01-01:b"]

    def test_legacy_training_identity_rewrite_backs_up_original_rows(
        self,
        tmp_path,
        monkeypatch,
    ):
        from app.bootstrap import schema as storage_schema

        test_db = tmp_path / "backup-training-identity.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        storage_schema.init_storage()
        legacy_log_id = "2026-01-01:bundle-1:session-1"
        with sqlite.connect() as con:
            con.execute(
                "INSERT INTO training_blocks (id, data, created_at, updated_at) "
                "VALUES ('block-1', ?, 'now', 'now')",
                (
                    json.dumps(
                        {
                            "status": "active",
                            "schedule_start": "2026-01-01",
                            "artifact": {
                                "bundle_ids": ["bundle-1"],
                                "window": {"start": "2026-01-01"},
                            },
                        }
                    ),
                ),
            )
            con.execute(
                "INSERT INTO training_bundles (id, data, created_at, updated_at) "
                "VALUES ('bundle-1', ?, 'now', 'now')",
                (json.dumps({"status": "active", "artifact": {"id": "bundle-1"}}),),
            )
            for table in ("training_registry", "training_exercise_library"):
                con.execute(
                    f'INSERT INTO "{table}" (id, data, created_at, updated_at) '
                    "VALUES ('singleton', ?, 'now', 'now')",
                    (json.dumps({"artifact": {}}),),
                )
            con.execute(
                "INSERT INTO training_card_logs (id, data, created_at, updated_at) "
                "VALUES (?, ?, 'now', 'now')",
                (
                    legacy_log_id,
                    json.dumps(
                        {
                            "id": legacy_log_id,
                            "date": "2026-01-01",
                            "occurrence_key": "bundle-1:session-1",
                        }
                    ),
                ),
            )
            con.commit()

        storage_schema.init_storage()

        backups = list((test_db.parent / "backups").glob("pre-migration-*.db"))
        assert len(backups) == 1
        with sqlite.connect(str(backups[0])) as con:
            block = con.execute(
                "SELECT data FROM training_blocks WHERE id = 'block-1'"
            ).fetchone()
            assert json.loads(block["data"]).get("program_instance_id") is None
            assert con.execute(
                "SELECT 1 FROM training_card_logs WHERE id = ?", (legacy_log_id,)
            ).fetchone() is not None
        with sqlite.connect() as con:
            assert storage_schema._destructive_migration_pending(con) is False

        storage_schema.init_storage()

        assert list((test_db.parent / "backups").glob("pre-migration-*.db")) == backups

    def test_legacy_coach_occurrence_rewrite_backs_up_original_rows(
        self,
        tmp_path,
        monkeypatch,
    ):
        from app.bootstrap import schema as storage_schema
        from app.domains.training.domain.instance_identity import program_instance_id

        test_db = tmp_path / "backup-coach-occurrence.db"
        monkeypatch.setattr(sqlite, "DB_PATH", test_db)
        storage_schema.init_storage()
        instance_id = program_instance_id(
            block={},
            bundles=[],
            registry={},
            library={},
            schedule_start="2026-01-01",
        )
        legacy_key = "bundle-1:session-1"
        with sqlite.connect() as con:
            con.execute(
                "INSERT INTO training_blocks (id, data, created_at, updated_at) "
                "VALUES ('block-1', ?, 'now', 'now')",
                (
                    json.dumps(
                        {
                            "status": "active",
                            "program_instance_id": instance_id,
                        }
                    ),
                ),
            )
            con.execute(
                "INSERT INTO coach_reviews "
                "(id, date, kind, run_id, occurrence_key, status, updated_at, data) "
                "VALUES ('review-1', '2026-01-01', 'run', 'run-1', ?, "
                "'complete', 'now', ?)",
                (legacy_key, json.dumps({"occurrence_key": legacy_key})),
            )
            con.commit()

        storage_schema.init_storage()

        backups = list((test_db.parent / "backups").glob("pre-migration-*.db"))
        assert len(backups) == 1
        with sqlite.connect(str(backups[0])) as con:
            backed_up = con.execute(
                "SELECT occurrence_key FROM coach_reviews WHERE id = 'review-1'"
            ).fetchone()
        assert backed_up["occurrence_key"] == legacy_key
        with sqlite.connect() as con:
            assert storage_schema._destructive_migration_pending(con) is False

        storage_schema.init_storage()

        assert list((test_db.parent / "backups").glob("pre-migration-*.db")) == backups


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
