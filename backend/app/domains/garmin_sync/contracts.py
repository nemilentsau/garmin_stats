"""Pydantic contracts owned by Garmin sync."""

from app.contracts.base import DefaultsRequired


class IngestResult(DefaultsRequired):
    days_ingested: int
    duration_ms: int


class IngestStatus(DefaultsRequired):
    needs_ingest: bool
    last_ingest_time: str | None = None
    days_in_db: int
    days_on_disk: int


class SyncResult(DefaultsRequired):
    downloaded: int
    skipped: int
    failed: int
    days_ingested: int
    duration_ms: int
    activities_downloaded: int
    activities_skipped: int
    activities_failed: int
    runs_ingested: int = 0
    runs_ingest_failed: int = 0


class RunningActivityIngestResult(DefaultsRequired):
    """Outcome of one running-activity ingest pass."""

    skipped: bool = False
    files_seen: int = 0
    sessions_ingested: int = 0
    files_failed: int = 0
