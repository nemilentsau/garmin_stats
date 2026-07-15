"""Tests for SQLite storage initialization and shared JSON persistence behavior."""

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
