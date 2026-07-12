"""Application lifespan wiring and startup ingest behavior."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .container import build_container
from .process_runtime import ProcessRuntime
from .schema import init_storage

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared storage and start process-owned runtime tasks."""
    init_storage()
    runtime = ProcessRuntime(build_container())
    runtime.start()
    try:
        yield
    finally:
        await runtime.stop()
