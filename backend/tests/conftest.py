"""Shared test fixtures."""

import pytest

import app.infra.database as db
import app.infra.sqlite as sqlite
from app.infra import cache


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Use a temporary DB for each test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(sqlite, "DB_PATH", test_db)
    cache.invalidate()
    db.init_db()
    yield test_db
