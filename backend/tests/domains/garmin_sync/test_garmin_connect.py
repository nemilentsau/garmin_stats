"""Tests for Garmin Connect infrastructure adapters."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.domains.garmin_sync.infra.garmin_connect import GarminConnectDownloadClient


class _FakeRawGarminClient:
    def __init__(
        self,
        responses: dict[str, bytes | bytearray | None] | None = None,
        *,
        activities: list[dict[str, Any]] | None = None,
        activity_payload: bytes | bytearray | None = None,
    ) -> None:
        self.responses = responses or {}
        self.paths: list[str] = []
        self._activities = activities if activities is not None else []
        self._activity_payload = activity_payload
        self.activity_queries: list[tuple[str, str]] = []

    def download(self, path: str) -> bytes | bytearray | None:
        self.paths.append(path)
        day = path.rsplit("/", maxsplit=1)[-1]
        return self.responses[day]

    def get_activities_by_date(
        self,
        startdate: str,
        enddate: str,
        activitytype: str | None = None,
        sortorder: str | None = None,
    ) -> list[dict[str, Any]]:
        self.activity_queries.append((startdate, enddate))
        return self._activities

    def download_activity(
        self, activity_id: str, dl_fmt: Any
    ) -> bytes | bytearray | None:
        return self._activity_payload


def test_wellness_client_downloads_expected_garmin_path_and_accepts_size_floor():
    raw_client = _FakeRawGarminClient({"2026-03-14": bytearray(b"x" * 100)})
    sleep_calls: list[float] = []
    client = GarminConnectDownloadClient(raw_client, sleep=sleep_calls.append)

    result = client.download_wellness_archive(date(2026, 3, 14))

    assert result == b"x" * 100
    assert raw_client.paths == ["/download-service/files/wellness/2026-03-14"]
    assert sleep_calls == []


def test_wellness_client_rejects_archives_below_size_floor():
    raw_client = _FakeRawGarminClient({"2026-03-14": b"x" * 99})
    client = GarminConnectDownloadClient(raw_client, sleep=lambda _seconds: None)

    assert client.download_wellness_archive(date(2026, 3, 14)) is None


def test_wellness_client_spaces_repeated_requests():
    raw_client = _FakeRawGarminClient({
        "2026-03-14": b"x" * 100,
        "2026-03-15": b"y" * 100,
    })
    sleep_calls: list[float] = []
    client = GarminConnectDownloadClient(
        raw_client,
        sleep=sleep_calls.append,
        request_spacing_seconds=2.5,
    )

    client.download_wellness_archive(date(2026, 3, 14))
    client.download_wellness_archive(date(2026, 3, 15))

    assert sleep_calls == [2.5]


def test_list_activities_maps_ids_and_skips_entries_without_id():
    raw_client = _FakeRawGarminClient(
        activities=[
            {"activityId": 23398049297, "activityName": "Morning Run"},
            {"activityName": "ghost entry"},
        ]
    )
    client = GarminConnectDownloadClient(raw_client, sleep=lambda _s: None)

    refs = client.list_activities(date(2026, 6, 27))

    assert [r.activity_id for r in refs] == ["23398049297"]
    assert refs[0].metadata["activityName"] == "Morning Run"
    assert raw_client.activity_queries == [("2026-06-27", "2026-06-27")]


def test_download_activity_original_returns_none_for_short_payload():
    raw_client = _FakeRawGarminClient(activity_payload=b"x")
    client = GarminConnectDownloadClient(raw_client, sleep=lambda _s: None)

    assert client.download_activity_original("123") is None


def test_download_activity_original_returns_bytes_for_real_payload():
    raw_client = _FakeRawGarminClient(activity_payload=b"P" * 200)
    client = GarminConnectDownloadClient(raw_client, sleep=lambda _s: None)

    assert client.download_activity_original("123") == b"P" * 200


def test_activity_and_wellness_requests_share_request_spacing():
    sleeps: list[float] = []
    raw_client = _FakeRawGarminClient(activities=[], activity_payload=b"P" * 200)
    client = GarminConnectDownloadClient(raw_client, sleep=sleeps.append)

    client.list_activities(date(2026, 6, 27))
    client.download_activity_original("123")

    assert sleeps == [1.0]
