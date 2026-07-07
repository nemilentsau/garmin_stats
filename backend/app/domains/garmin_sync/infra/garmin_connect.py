"""Garmin Connect client adapters for Garmin sync."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from garminconnect import Garmin

from app.domains.garmin_sync.dependencies import ActivityRef, GarminDownloadClient

_WELLNESS_ARCHIVE_PATH_PREFIX = "/download-service/files/wellness"
_MINIMUM_ARCHIVE_BYTES = 100
_MINIMUM_ACTIVITY_BYTES = 100
_REQUEST_SPACING_SECONDS = 1.0


class _RawGarminClient(Protocol):
    def download(self, path: str) -> bytes | bytearray | None: ...

    def get_activities_by_date(
        self,
        startdate: str,
        enddate: str,
        activitytype: str | None = None,
        sortorder: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def download_activity(
        self, activity_id: str, dl_fmt: Any
    ) -> bytes | bytearray | None: ...


class GarminConnectDownloadClient:
    """Download wellness archives and original activity payloads via Garmin Connect."""

    def __init__(
        self,
        client: _RawGarminClient,
        *,
        sleep: Callable[[float], None],
        request_spacing_seconds: float = _REQUEST_SPACING_SECONDS,
    ) -> None:
        self._client = client
        self._sleep = sleep
        self._request_spacing_seconds = request_spacing_seconds
        self._has_requested = False

    def download_wellness_archive(self, day: date) -> bytes | None:
        self._space_requests()
        data = self._client.download(f"{_WELLNESS_ARCHIVE_PATH_PREFIX}/{day.isoformat()}")
        if not data or len(data) < _MINIMUM_ARCHIVE_BYTES:
            return None
        return bytes(data)

    def list_activities(self, day: date) -> list[ActivityRef]:
        self._space_requests()
        date_str = day.isoformat()
        activities = self._client.get_activities_by_date(date_str, date_str, sortorder="asc")
        refs: list[ActivityRef] = []
        for activity in activities:
            activity_id = activity.get("activityId")
            if activity_id is None:
                continue
            refs.append(ActivityRef(activity_id=str(activity_id), metadata=activity))
        return refs

    def download_activity_original(self, activity_id: str) -> bytes | None:
        self._space_requests()
        data = self._client.download_activity(
            activity_id, Garmin.ActivityDownloadFormat.ORIGINAL
        )
        if not data or len(data) < _MINIMUM_ACTIVITY_BYTES:
            return None
        return bytes(data)

    def _space_requests(self) -> None:
        if self._has_requested:
            self._sleep(self._request_spacing_seconds)
        self._has_requested = True


class GarminConnectClientFactory:
    """Create Garmin download clients from saved token-directory login state."""

    def __init__(self, token_dir: Path) -> None:
        self._token_dir = token_dir

    def create(self) -> GarminDownloadClient:
        token_path = self._token_dir
        if not token_path.is_dir():
            raise RuntimeError(
                f"No Garmin tokens found at {token_path}. "
                "Run `scripts/download_garmin.py --login` first."
            )
        client = Garmin()
        client.login(str(token_path))
        return GarminConnectDownloadClient(client, sleep=time.sleep)
