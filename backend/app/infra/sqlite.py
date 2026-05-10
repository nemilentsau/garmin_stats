"""SQLite connection primitives shared by persistence adapters."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from app.core.config import get_app_config

_APP_CONFIG = get_app_config()

DB_PATH = _APP_CONFIG.database_path


@contextmanager
def connect(db_path: str | None = None) -> Generator[sqlite3.Connection]:
    """Yield a sqlite3 connection with Row factory; close on exit."""
    con = sqlite3.connect(str(db_path or DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
