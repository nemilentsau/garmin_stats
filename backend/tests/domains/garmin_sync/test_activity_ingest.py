"""Activity ingest engine: fingerprint gating, idempotence, tolerant parse.

Covers the state matrix required for filesystem/startup-adjacent ingest code:
missing source dir, first run, unchanged-tree skip, stale-tree delta parsing,
per-file failure tolerance, the ``force`` bypass of the fingerprint gate, lap
persistence, and cache invalidation gated strictly on rows actually written.
Builders are declared locally (not imported from the garmin_health test
module) to keep this test file independent of that domain's test fixtures.
"""

from pathlib import Path

import app.domains.garmin_sync.infra.activity_ingest as ingest_mod
from app.domains.garmin_health.contracts import (
    RunningActivityData,
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
)
from app.domains.garmin_sync.infra.activity_ingest import ingest_running_activities
from app.infra import cache
from app.infra.sqlite import connect


def _session(
    source_file: str, sid: str, laps: list[RunningActivityLap] | None = None
) -> RunningActivityData:
    return RunningActivityData(
        session=RunningActivitySession(
            id=sid,
            source_file=source_file,
            session_date="2026-07-10",
            start_time_local="2026-07-10T10:57:26",
        ),
        laps=laps or [],
        series=RunningActivitySeries(elapsed_s=[0, 1], heart_rate_bpm=[140, 141]),
    )


def _fake_parse(fit_path: Path, activities_dir: Path) -> RunningActivityData:
    rel = str(fit_path.relative_to(activities_dir))
    return _session(rel, f"id-{fit_path.stem}")


def _write_fit(activities_dir: Path, day: str, stem: str) -> Path:
    day_dir = activities_dir / day
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{stem}.fit"
    path.write_bytes(b"fake")
    return path


def _session_count() -> int:
    with connect() as con:
        return con.execute("SELECT COUNT(*) AS n FROM running_activity_sessions").fetchone()["n"]


class TestActivityIngest:
    def test_missing_dir_is_a_clean_noop(self, tmp_path):
        result = ingest_running_activities(tmp_path / "nope")
        assert result.sessions_ingested == 0
        assert result.skipped is False
        assert _session_count() == 0

    def test_first_run_ingests_all_running_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "parse_running_activity", _fake_parse)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")
        _write_fit(tmp_path, "2026-07-09", "064500_running_generic")

        result = ingest_running_activities(tmp_path)

        assert result.sessions_ingested == 2
        assert result.skipped is False
        assert _session_count() == 2
        with connect() as con:
            row = con.execute(
                "SELECT session_id, data FROM running_activity_series LIMIT 1"
            ).fetchone()
        assert row is not None

    def test_second_run_with_unchanged_tree_is_skipped_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "parse_running_activity", _fake_parse)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")
        ingest_running_activities(tmp_path)

        def _boom(*args, **kwargs):
            raise AssertionError("must not parse on unchanged tree")

        monkeypatch.setattr(ingest_mod, "parse_running_activity", _boom)
        result = ingest_running_activities(tmp_path)

        assert result.skipped is True
        assert result.sessions_ingested == 0
        assert _session_count() == 1

    def test_stale_tree_ingests_only_new_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "parse_running_activity", _fake_parse)
        _write_fit(tmp_path, "2026-07-09", "064500_running_generic")
        ingest_running_activities(tmp_path)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")

        result = ingest_running_activities(tmp_path)

        assert result.skipped is False
        assert result.sessions_ingested == 1
        assert _session_count() == 2

    def test_broken_file_counts_failed_and_rest_ingests(self, tmp_path, monkeypatch):
        def _flaky(fit_path: Path, activities_dir: Path) -> RunningActivityData:
            if "broken" in fit_path.name:
                raise ValueError("corrupt")
            return _fake_parse(fit_path, activities_dir)

        monkeypatch.setattr(ingest_mod, "parse_running_activity", _flaky)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")
        _write_fit(tmp_path, "2026-07-09", "064500_running_broken")

        result = ingest_running_activities(tmp_path)

        assert result.sessions_ingested == 1
        assert result.files_failed == 1

    def test_force_true_bypasses_fingerprint_skip_on_unchanged_tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "parse_running_activity", _fake_parse)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")
        ingest_running_activities(tmp_path)

        def _boom(*args, **kwargs):
            raise AssertionError("must not re-parse an already-ingested file")

        monkeypatch.setattr(ingest_mod, "parse_running_activity", _boom)
        result = ingest_running_activities(tmp_path, force=True)

        # force bypasses the fingerprint-equality skip (skipped is False, not
        # True as the unforced case would report), but delta-by-source_file
        # still holds: there is nothing new to parse, so no exception fires.
        assert result.skipped is False
        assert result.sessions_ingested == 0
        assert _session_count() == 1

    def test_ingest_persists_laps_alongside_session_and_series(self, tmp_path, monkeypatch):
        lap = RunningActivityLap(lap_index=0, distance_m=1000.0)

        def _parse_with_lap(fit_path: Path, activities_dir: Path) -> RunningActivityData:
            rel = str(fit_path.relative_to(activities_dir))
            return _session(rel, "id-with-lap", laps=[lap])

        monkeypatch.setattr(ingest_mod, "parse_running_activity", _parse_with_lap)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")

        result = ingest_running_activities(tmp_path)

        assert result.sessions_ingested == 1
        with connect() as con:
            rows = con.execute(
                "SELECT lap_index, data FROM running_activity_laps WHERE session_id = ?",
                ("id-with-lap",),
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["lap_index"] == 0


class TestActivityIngestCacheInvalidation:
    def test_cache_invalidated_when_new_sessions_are_ingested(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "parse_running_activity", _fake_parse)
        calls: list[int] = []
        monkeypatch.setattr(cache, "invalidate", lambda: calls.append(1))
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")

        ingest_running_activities(tmp_path)

        assert len(calls) == 1

    def test_cache_not_invalidated_when_tree_unchanged_and_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "parse_running_activity", _fake_parse)
        _write_fit(tmp_path, "2026-07-10", "105726_running_generic")
        ingest_running_activities(tmp_path)

        calls: list[int] = []
        monkeypatch.setattr(cache, "invalidate", lambda: calls.append(1))
        result = ingest_running_activities(tmp_path)

        assert result.skipped is True
        assert calls == []

    def test_cache_not_invalidated_when_all_new_files_fail_to_parse(self, tmp_path, monkeypatch):
        def _always_fails(fit_path: Path, activities_dir: Path) -> RunningActivityData:
            raise ValueError("corrupt")

        monkeypatch.setattr(ingest_mod, "parse_running_activity", _always_fails)
        calls: list[int] = []
        monkeypatch.setattr(cache, "invalidate", lambda: calls.append(1))
        _write_fit(tmp_path, "2026-07-10", "105726_running_broken")

        result = ingest_running_activities(tmp_path)

        assert result.files_failed == 1
        assert result.sessions_ingested == 0
        assert calls == []
