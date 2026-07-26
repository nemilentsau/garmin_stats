"""Tests for Garmin sync ingest workflows.

These cases cover the workflow policy around archive reconciliation, mutable
Garmin download ranges, incremental ingest, and watcher state transitions during
bulk sync.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from itertools import count
from pathlib import Path

import pytest

from app.domains.garmin_sync.contracts import (
    IngestResult,
    IngestStatus,
    RunningActivityIngestResult,
)
from app.domains.garmin_sync.dependencies import ActivityRef, GarminSyncDependencies
from app.domains.garmin_sync.workflows import (
    _plan_activity_dates,
    _plan_sync_dates,
    get_ingest_status,
    sync_garmin,
    trigger_ingest,
)


class FakeIngestGateway:
    def __init__(self) -> None:
        self.status = IngestStatus(
            needs_ingest=False,
            last_ingest_time="2026-03-15T00:00:00Z",
            days_in_db=2,
            days_on_disk=2,
        )
        self.ingest_all_result = IngestResult(days_ingested=2, duration_ms=50)
        self.ingest_dates_result = IngestResult(days_ingested=1, duration_ms=25)
        self.ingest_dates_error: RuntimeError | None = None
        self.calls: list[tuple[str, Path, list[str] | None]] = []
        self.running_result = RunningActivityIngestResult(sessions_ingested=2)
        self.running_calls: list[Path] = []

    def check_status(self, data_dir: Path) -> IngestStatus:
        self.calls.append(("status", data_dir, None))
        return self.status

    def ingest_all(self, data_dir: Path) -> IngestResult:
        self.calls.append(("ingest_all", data_dir, None))
        return self.ingest_all_result

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        self.calls.append(("ingest_dates", data_dir, dates))
        if self.ingest_dates_error is not None:
            raise self.ingest_dates_error
        return self.ingest_dates_result

    def ingest_running_activities(
        self, activities_dir: Path, force: bool = False
    ) -> RunningActivityIngestResult:
        self.running_calls.append(activities_dir)
        return self.running_result


class FakeGarminClient:
    def __init__(
        self,
        responses: dict[str, bytes | None],
        *,
        activities: dict[str, list[ActivityRef]] | None = None,
        activity_payloads: dict[str, bytes | None] | None = None,
        listing_errors: set[str] | None = None,
    ) -> None:
        self.responses = responses
        self.days: list[date] = []
        self.activities = activities or {}
        self.activity_payloads = activity_payloads or {}
        self.listing_errors = listing_errors or set()
        self.listed_days: list[str] = []
        self.downloaded_activities: list[str] = []

    def download_wellness_archive(self, day: date) -> bytes | None:
        self.days.append(day)
        return self.responses[day.isoformat()]

    def list_activities(self, day: date) -> list[ActivityRef]:
        date_str = day.isoformat()
        self.listed_days.append(date_str)
        if date_str in self.listing_errors:
            raise RuntimeError("listing failed")
        return self.activities.get(date_str, [])

    def download_activity_original(self, activity_id: str) -> bytes | None:
        self.downloaded_activities.append(activity_id)
        return self.activity_payloads.get(activity_id)


class FakeActivityFileStore:
    def __init__(self, *, existing: set[tuple[str, str]] | None = None) -> None:
        self.existing = existing if existing is not None else set()
        self.stored: list[tuple[Path, str, str]] = []
        self.store_error: Exception | None = None

    def has_activity(self, activities_dir: Path, day: date, activity_id: str) -> bool:
        return (day.isoformat(), activity_id) in self.existing

    def store_activity(
        self,
        activities_dir: Path,
        day: date,
        activity_id: str,
        metadata: dict,
        payload: bytes,
    ) -> None:
        if self.store_error is not None:
            raise self.store_error
        self.stored.append((activities_dir, day.isoformat(), activity_id))
        self.existing.add((day.isoformat(), activity_id))


class FakeGarminClientFactory:
    def __init__(self, client: FakeGarminClient) -> None:
        self.client = client
        self.calls = 0

    def create(self) -> FakeGarminClient:
        self.calls += 1
        return self.client


class FakeSyncFileStore:
    def __init__(self, *, latest: date | None, existing: set[date]) -> None:
        self.latest = latest
        self.existing = existing
        self.installed: list[tuple[Path, date, bytes]] = []
        self.install_error: Exception | None = None

    def latest_zip_date(self, data_dir: Path) -> date | None:
        return self.latest

    def zip_exists(self, data_dir: Path, day: date) -> bool:
        return day in self.existing

    def install_archive(self, data_dir: Path, day: date, data: bytes) -> None:
        if self.install_error is not None:
            raise self.install_error
        self.installed.append((data_dir, day, data))
        self.existing.add(day)


def _deps(
    tmp_path: Path,
    *,
    latest: date | None = date(2026, 3, 14),
    today: date = date(2026, 3, 15),
    existing: set[date] | None = None,
    responses: dict[str, bytes | None] | None = None,
    activities: dict[str, list[ActivityRef]] | None = None,
    activity_payloads: dict[str, bytes | None] | None = None,
    listing_errors: set[str] | None = None,
    existing_activities: set[tuple[str, str]] | None = None,
    extracted_dates: list[str] | None = None,
) -> tuple[
    GarminSyncDependencies,
    FakeIngestGateway,
    list[Path],
    list[str],
    FakeGarminClient,
    FakeSyncFileStore,
    FakeActivityFileStore,
]:
    ingest = FakeIngestGateway()
    archive_calls: list[Path] = []
    watcher_calls: list[str] = []
    extracted_dates = extracted_dates or []
    # An unbounded counter (not a fixed two-item list) because tests that call
    # sync_garmin more than once (e.g. to exercise idempotent activity skips)
    # need the fake clock to keep advancing rather than running dry.
    monotonic_values = count(10.0, 1.25)

    def extract_archives(data_dir: Path) -> list[str]:
        archive_calls.append(data_dir)
        return list(extracted_dates)

    def suspend_watcher() -> None:
        watcher_calls.append("suspend")

    def resume_watcher() -> None:
        watcher_calls.append("resume")

    def mark_watcher_synced() -> None:
        watcher_calls.append("synced")

    client = FakeGarminClient(
        responses
        or {
            "2026-03-14": b"x" * 101,
            "2026-03-15": b"y" * 101,
            "2026-03-16": b"z" * 101,
        },
        activities=activities,
        activity_payloads=activity_payloads,
        listing_errors=listing_errors,
    )
    files = FakeSyncFileStore(
        latest=latest,
        existing=existing if existing is not None else {date(2026, 3, 15)},
    )
    store = FakeActivityFileStore(existing=existing_activities)
    deps = GarminSyncDependencies(
        data_dir=tmp_path,
        activities_dir=tmp_path / "garmin_activities",
        ingest=ingest,
        extract_archives=extract_archives,
        suspend_watcher=suspend_watcher,
        resume_watcher=resume_watcher,
        mark_watcher_synced=mark_watcher_synced,
        clients=FakeGarminClientFactory(client),
        files=files,
        activity_files=store,
        today=lambda: today,
        monotonic=lambda: next(monotonic_values),
    )
    return deps, ingest, archive_calls, watcher_calls, client, files, store


def test_trigger_ingest_reconciles_archives_before_ingesting(tmp_path: Path):
    deps, ingest, archives, *_ = _deps(tmp_path)

    result = trigger_ingest(deps)

    assert result == IngestResult(days_ingested=2, duration_ms=50)
    assert archives == [tmp_path]
    assert ingest.calls == [("ingest_all", tmp_path, None)]


def test_trigger_ingest_refreshes_data_dependents_after_success(tmp_path: Path):
    deps, *_ = _deps(tmp_path)
    refreshes: list[str] = []
    deps = replace(
        deps,
        after_data_change=lambda: refreshes.append("experiments") or 1,
    )

    trigger_ingest(deps)

    assert refreshes == ["experiments"]


def test_trigger_ingest_keeps_successful_result_when_refresh_fails(tmp_path: Path):
    deps, *_ = _deps(tmp_path)

    def fail_refresh() -> int:
        raise RuntimeError("analysis unavailable")

    deps = replace(deps, after_data_change=fail_refresh)

    result = trigger_ingest(deps)

    assert result == IngestResult(days_ingested=2, duration_ms=50)


def test_get_ingest_status_reads_current_data_root_status(tmp_path: Path):
    deps, ingest, *_ = _deps(tmp_path)

    assert get_ingest_status(deps) == ingest.status
    assert ingest.calls == [("status", tmp_path, None)]


def test_sync_replaces_latest_day_downloads_range_and_ingests_affected_dates(
    tmp_path: Path,
):
    deps, ingest, archives, watcher, client, files, _store = _deps(tmp_path)

    result = sync_garmin(deps)

    assert result.downloaded == 1
    assert result.skipped == 1
    assert result.failed == 0
    assert result.days_ingested == 1
    assert result.duration_ms == 1250
    assert files.installed == [(tmp_path, date(2026, 3, 14), b"x" * 101)]
    assert client.days == [date(2026, 3, 14)]
    assert archives == [tmp_path]
    assert ingest.calls == [("ingest_dates", tmp_path, ["2026-03-14"])]
    assert watcher == ["suspend", "synced", "resume"]


def test_sync_refreshes_data_dependents_after_wellness_and_activity_ingest(tmp_path: Path):
    deps, *_ = _deps(tmp_path)
    refreshes: list[str] = []
    deps = replace(
        deps,
        after_data_change=lambda: refreshes.append("experiments") or 1,
    )

    sync_garmin(deps)

    assert refreshes == ["experiments"]


def test_sync_redownloads_latest_archive_through_today(tmp_path: Path):
    deps, ingest, _archives, _watcher, client, files, _store = _deps(
        tmp_path,
        today=date(2026, 3, 16),
    )

    result = sync_garmin(deps)

    assert result.downloaded == 2
    assert result.skipped == 1
    assert files.installed == [
        (tmp_path, date(2026, 3, 14), b"x" * 101),
        (tmp_path, date(2026, 3, 16), b"z" * 101),
    ]
    assert client.days == [date(2026, 3, 14), date(2026, 3, 16)]
    assert ingest.calls == [
        ("ingest_dates", tmp_path, ["2026-03-14", "2026-03-16"]),
    ]


def test_sync_starts_with_yesterday_when_no_archives_exist(tmp_path: Path):
    deps, ingest, _archives, watcher, client, files, _store = _deps(
        tmp_path,
        latest=None,
        existing=set(),
    )

    result = sync_garmin(deps)

    assert result.downloaded == 2
    assert client.days == [date(2026, 3, 14), date(2026, 3, 15)]
    assert ingest.calls == [
        ("ingest_dates", tmp_path, ["2026-03-14", "2026-03-15"]),
    ]
    assert watcher == ["suspend", "synced", "resume"]


def test_sync_treats_missing_archive_response_as_failed(tmp_path: Path):
    deps, _ingest, _archives, _watcher, client, files, _store = _deps(
        tmp_path,
        today=date(2026, 3, 14),
        responses={"2026-03-14": None},
    )

    result = sync_garmin(deps)

    assert result.downloaded == 0
    assert result.failed == 1
    assert files.installed == []
    assert client.days == [date(2026, 3, 14)]

    # The unchanged archive was never replaced, so no incremental ingest is needed.
    assert _ingest.calls == [("ingest_dates", tmp_path, [])]


def test_sync_treats_archive_install_failure_as_failed_without_ingesting_day(
    tmp_path: Path,
):
    deps, ingest, _archives, _watcher, _client, files, _store = _deps(
        tmp_path,
        today=date(2026, 3, 14),
    )
    files.install_error = ValueError("invalid replacement")

    result = sync_garmin(deps)

    assert result.downloaded == 0
    assert result.failed == 1
    assert files.installed == []
    assert ingest.calls == [("ingest_dates", tmp_path, [])]


def test_sync_ingests_dates_whose_archives_extraction_refreshed(tmp_path: Path):
    """An archive replaced outside the app is extracted by sync but was never
    ingested, while sync still stamped a whole-tree fingerprint over it — so the
    day stayed stale through every later startup and sync."""
    deps, ingest, _archives, _watcher, _client, _files, _store = _deps(
        tmp_path,
        today=date(2026, 3, 14),
        responses={"2026-03-14": None},
        extracted_dates=["2026-03-01"],
    )

    sync_garmin(deps)

    assert ingest.calls == [("ingest_dates", tmp_path, ["2026-03-01"])]


def test_sync_ingests_the_union_of_downloaded_and_extracted_dates(tmp_path: Path):
    deps, ingest, *_ = _deps(
        tmp_path,
        extracted_dates=["2026-03-14", "2026-03-01"],
    )

    sync_garmin(deps)

    assert ingest.calls == [
        ("ingest_dates", tmp_path, ["2026-03-01", "2026-03-14"]),
    ]


def test_sync_second_run_adds_no_dates_when_extraction_reports_nothing(tmp_path: Path):
    """Idempotence: with no external archive change, a repeat sync ingests only
    the mutable latest day it re-downloaded, never a growing set."""
    deps, ingest, *_ = _deps(tmp_path, today=date(2026, 3, 14))

    sync_garmin(deps)
    first = list(ingest.calls)
    ingest.calls.clear()
    sync_garmin(deps)

    assert first == [("ingest_dates", tmp_path, ["2026-03-14"])]
    assert ingest.calls == first


def test_sync_resumes_watcher_when_ingest_fails(tmp_path: Path):
    deps, ingest, _archives, watcher, _client, _files, _store = _deps(tmp_path)
    ingest.ingest_dates_error = RuntimeError("Ingest already in progress")

    with pytest.raises(RuntimeError, match="Ingest already in progress"):
        sync_garmin(deps)

    assert watcher == ["suspend", "resume"]


def test_sync_does_not_mark_watcher_synced_when_ingest_fails(tmp_path: Path):
    deps, ingest, _archives, watcher, _client, _files, _store = _deps(tmp_path)
    ingest.ingest_dates_error = RuntimeError("Ingest already in progress")

    with pytest.raises(RuntimeError, match="Ingest already in progress"):
        sync_garmin(deps)

    assert "synced" not in watcher


def test_plan_with_no_archives_starts_yesterday():
    plan = _plan_sync_dates(latest=None, today=date(2026, 3, 15))

    assert plan.refresh_latest is None
    assert plan.dates == [date(2026, 3, 14), date(2026, 3, 15)]


def test_plan_with_older_latest_archive_redownloads_from_latest_through_today():
    plan = _plan_sync_dates(latest=date(2026, 3, 14), today=date(2026, 3, 16))

    assert plan.refresh_latest == date(2026, 3, 14)
    assert plan.dates == [date(2026, 3, 14), date(2026, 3, 15), date(2026, 3, 16)]


def test_plan_with_latest_archive_at_today_re_syncs_only_today():
    plan = _plan_sync_dates(latest=date(2026, 3, 15), today=date(2026, 3, 15))

    assert plan.refresh_latest == date(2026, 3, 15)
    assert plan.dates == [date(2026, 3, 15)]


def _ref(activity_id: str) -> ActivityRef:
    return ActivityRef(activity_id=activity_id, metadata={"activityId": activity_id})


def test_sync_sweeps_activity_window_with_lookback_and_stores_new(tmp_path: Path):
    deps, _ingest, _archives, _watcher, client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-12": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )

    result = sync_garmin(deps)

    assert client.listed_days == ["2026-03-12", "2026-03-13", "2026-03-14", "2026-03-15"]
    assert [entry[2] for entry in store.stored] == ["a1"]
    activity_counts = (
        result.activities_downloaded,
        result.activities_skipped,
        result.activities_failed,
    )
    assert activity_counts == (1, 0, 0)


def test_sync_second_run_skips_already_stored_activities(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-13": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )

    first = sync_garmin(deps)
    second = sync_garmin(deps)

    assert first.activities_downloaded == 1
    assert second.activities_downloaded == 0
    assert second.activities_skipped == 1
    assert [entry[2] for entry in store.stored] == ["a1"]


def test_sync_activity_listing_failure_is_counted_and_isolated(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, _store = _deps(
        tmp_path,
        activities={"2026-03-15": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
        listing_errors={"2026-03-12"},
    )

    result = sync_garmin(deps)

    assert result.activities_failed == 1
    assert result.activities_downloaded == 1
    assert result.days_ingested == 1  # wellness ingest unaffected


def test_sync_counts_activity_without_payload_as_failed(tmp_path: Path):
    deps, *_rest, _files, _store = _deps(
        tmp_path,
        activities={"2026-03-14": [_ref("a1")]},
    )

    result = sync_garmin(deps)

    assert (result.activities_downloaded, result.activities_failed) == (0, 1)


def test_sync_counts_unusable_activity_payload_as_failed(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-14": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )
    store.store_error = ValueError("activity ZIP contained no FIT files")

    result = sync_garmin(deps)

    assert (result.activities_downloaded, result.activities_failed) == (0, 1)


def test_sync_counts_activity_store_oserror_as_failed(tmp_path: Path):
    deps, _ingest, _archives, _watcher, _client, _files, store = _deps(
        tmp_path,
        activities={"2026-03-14": [_ref("a1")]},
        activity_payloads={"a1": b"payload"},
    )
    store.store_error = OSError("disk full")

    result = sync_garmin(deps)

    assert (result.activities_downloaded, result.activities_failed) == (0, 1)
    assert result.days_ingested == 1


def test_sync_tolerates_future_dated_latest_archive(tmp_path: Path):
    deps, *_rest = _deps(tmp_path, latest=date(2026, 3, 16), responses={})

    result = sync_garmin(deps)

    assert result.downloaded == 0


def test_plan_activity_dates_applies_lookback_beyond_wellness_start():
    days = _plan_activity_dates(wellness_start=date(2026, 3, 14), today=date(2026, 3, 15))

    assert days == [date(2026, 3, 12), date(2026, 3, 13), date(2026, 3, 14), date(2026, 3, 15)]


def test_plan_activity_dates_keeps_older_wellness_start():
    days = _plan_activity_dates(wellness_start=date(2026, 3, 10), today=date(2026, 3, 15))

    assert days[0] == date(2026, 3, 10)
    assert days[-1] == date(2026, 3, 15)


def test_sync_ingests_running_activities_after_download(tmp_path: Path):
    deps, ingest, *_ = _deps(tmp_path)

    result = sync_garmin(deps)

    assert ingest.running_calls == [deps.activities_dir]
    assert result.runs_ingested == 2
    assert result.runs_ingest_failed == 0


def test_sync_threads_running_activity_failures_into_result(tmp_path: Path):
    deps, ingest, *_ = _deps(tmp_path)
    ingest.running_result = RunningActivityIngestResult(sessions_ingested=1, files_failed=3)

    result = sync_garmin(deps)

    assert result.runs_ingested == 1
    assert result.runs_ingest_failed == 3
