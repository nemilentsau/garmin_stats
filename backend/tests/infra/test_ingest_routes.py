"""Tests for ingest routes."""

import pytest
from fastapi import HTTPException

import app.routers.ingest as ingest_mod
from app.models import IngestResult, IngestStatus


class TestIngestRoutes:
    def test_trigger_ingest_reconciles_archives_before_ingesting(self, monkeypatch):
        order: list[str] = []

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 2

        expected = IngestResult(days_ingested=45, duration_ms=987)

        def fake_ingest_all(_data_dir):
            assert order == ["extract"]
            order.append("ingest")
            return expected

        monkeypatch.setattr(ingest_mod, "extract_existing_archives", fake_extract_existing_archives)
        monkeypatch.setattr(ingest_mod, "ingest_all", fake_ingest_all)

        result = ingest_mod.trigger_ingest()

        assert result == expected
        assert order == ["extract", "ingest"]

    def test_trigger_ingest_returns_409_when_ingest_busy(self, monkeypatch):
        monkeypatch.setattr(ingest_mod, "extract_existing_archives", lambda _data_dir: 0)
        monkeypatch.setattr(
            ingest_mod,
            "ingest_all",
            lambda _data_dir: (_ for _ in ()).throw(RuntimeError("Ingest already in progress")),
        )

        with pytest.raises(HTTPException, match="Ingest already in progress") as exc_info:
            ingest_mod.trigger_ingest()

        assert exc_info.value.status_code == 409

    def test_get_ingest_status_returns_database_status(self, monkeypatch):
        expected = IngestStatus(
            needs_ingest=True,
            last_ingest_time="2026-03-15T00:00:00Z",
            days_in_db=58,
            days_on_disk=72,
        )
        monkeypatch.setattr(ingest_mod, "check_ingest_status", lambda _data_dir: expected)

        assert ingest_mod.get_ingest_status() == expected
