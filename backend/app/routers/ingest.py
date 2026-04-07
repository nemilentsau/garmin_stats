"""Ingest HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..infra.database import DATA_DIR, check_ingest_status, ingest_all
from ..infra.watcher import extract_existing_archives
from ..models import IngestResult, IngestStatus, SyncResult
from ..services.garmin_sync import sync_garmin

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("", response_model=IngestResult)
def trigger_ingest():
    """Re-ingest all FIT files into the database."""
    try:
        extract_existing_archives(DATA_DIR)
        return ingest_all(DATA_DIR)
    except RuntimeError as err:
        raise HTTPException(
            status_code=409, detail="Ingest already in progress",
        ) from err


@router.get("/status", response_model=IngestStatus)
def get_ingest_status():
    """Check whether new data needs ingesting."""
    return check_ingest_status(DATA_DIR)


@router.post("/sync", response_model=SyncResult)
def trigger_sync():
    """Download new data from Garmin Connect and ingest."""
    try:
        return sync_garmin(DATA_DIR)
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
