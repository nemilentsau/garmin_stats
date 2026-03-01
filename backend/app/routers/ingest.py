"""Ingest HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..database import DATA_DIR, check_ingest_status, ingest_all
from ..models import IngestResult, IngestStatus

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("", response_model=IngestResult)
def trigger_ingest():
    """Re-ingest all FIT files into the database."""
    try:
        return ingest_all(DATA_DIR)
    except RuntimeError as err:
        raise HTTPException(
            status_code=409, detail="Ingest already in progress",
        ) from err


@router.get("/status", response_model=IngestStatus)
def get_ingest_status():
    """Check whether new data needs ingesting."""
    return check_ingest_status(DATA_DIR)
