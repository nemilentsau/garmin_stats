"""Shared test fixtures."""

import pytest

import app.bootstrap.schema as storage_schema
import app.domains.assistant.adapters as assistant_db
import app.infra.sqlite as sqlite
from app.infra import cache


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Use a temporary DB for each test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(sqlite, "DB_PATH", test_db)
    cache.invalidate()
    storage_schema.init_storage()
    assistant_db.migrate_assistant_storage()
    yield test_db
