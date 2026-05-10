"""Application lifespan wiring and startup ingest behavior."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..infra.database import init_db
from .container import build_container
from .process_runtime import ProcessRuntime

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, auto-ingest if empty, start file watcher."""
    init_db()
    runtime = ProcessRuntime(build_container())
    runtime.start()
    yield
    runtime.stop()
