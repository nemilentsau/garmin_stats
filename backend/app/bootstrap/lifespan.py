"""Application lifespan wiring and startup ingest behavior."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.domains.assistant.adapters import migrate_assistant_storage

from .container import build_container
from .process_runtime import ProcessRuntime
from .schema import init_storage

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init shared DB, run domain storage migrations, then start runtime."""
    init_storage()
    migrate_assistant_storage()
    runtime = ProcessRuntime(build_container())
    runtime.start()
    yield
    runtime.stop()
