"""Tests for Garmin Connect infrastructure adapters."""

from __future__ import annotations

from datetime import date

from app.domains.garmin_sync.infra.garmin_connect import GarminConnectWellnessClient


class _FakeRawGarminClient:
    def __init__(self, responses: dict[str, bytes | bytearray | None]) -> None:
        self.responses = responses
        self.paths: list[str] = []

    def download(self, path: str) -> bytes | bytearray | None:
        self.paths.append(path)
        day = path.rsplit("/", maxsplit=1)[-1]
        return self.responses[day]


def test_wellness_client_downloads_expected_garmin_path_and_accepts_size_floor():
    raw_client = _FakeRawGarminClient({"2026-03-14": bytearray(b"x" * 100)})
    sleep_calls: list[float] = []
    client = GarminConnectWellnessClient(raw_client, sleep=sleep_calls.append)

    result = client.download_wellness_archive(date(2026, 3, 14))

    assert result == b"x" * 100
    assert raw_client.paths == ["/download-service/files/wellness/2026-03-14"]
    assert sleep_calls == []


def test_wellness_client_rejects_archives_below_size_floor():
    raw_client = _FakeRawGarminClient({"2026-03-14": b"x" * 99})
    client = GarminConnectWellnessClient(raw_client, sleep=lambda _seconds: None)

    assert client.download_wellness_archive(date(2026, 3, 14)) is None


def test_wellness_client_spaces_repeated_requests():
    raw_client = _FakeRawGarminClient({
        "2026-03-14": b"x" * 100,
        "2026-03-15": b"y" * 100,
    })
    sleep_calls: list[float] = []
    client = GarminConnectWellnessClient(
        raw_client,
        sleep=sleep_calls.append,
        request_spacing_seconds=2.5,
    )

    client.download_wellness_archive(date(2026, 3, 14))
    client.download_wellness_archive(date(2026, 3, 15))

    assert sleep_calls == [2.5]
