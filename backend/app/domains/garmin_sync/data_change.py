"""Best-effort notification for read models derived from Garmin data."""

from __future__ import annotations

import logging

from app.domains.garmin_sync.dependencies import GarminSyncDependencies

log = logging.getLogger(__name__)


def notify_data_changed(deps: GarminSyncDependencies) -> None:
    """Refresh cross-domain read models without falsifying ingest success."""
    try:
        deps.after_data_change()
    except Exception:
        log.exception("Post-ingest data refresh failed; ingest result is unaffected")
