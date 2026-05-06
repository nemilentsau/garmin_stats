"""Ingest HTTP routes."""

from fastapi import APIRouter, HTTPException

from app.bootstrap.container import build_container
from app.domains.garmin_sync import workflows
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus, SyncResult

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("", response_model=IngestResult)
def trigger_ingest():
    """Re-ingest all FIT files into the database."""
    try:
        return workflows.trigger_ingest(build_container().garmin_sync)
    except RuntimeError as err:
        raise HTTPException(
            status_code=409,
            detail="Ingest already in progress",
        ) from err


@router.get("/status", response_model=IngestStatus)
def get_ingest_status():
    """Check whether new data needs ingesting."""
    return workflows.get_ingest_status(build_container().garmin_sync)


@router.post("/sync", response_model=SyncResult)
def trigger_sync():
    """Download new data from Garmin Connect and ingest."""
    try:
        return workflows.sync_garmin(build_container().garmin_sync)
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
