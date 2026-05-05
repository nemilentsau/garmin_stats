"""Tests for the days router endpoints."""

import pytest
from fastapi import HTTPException

import app.routers.days as days_mod


class TestGetDay:
    def test_returns_404_when_day_not_ingested(self, monkeypatch):
        monkeypatch.setattr(days_mod, "load_available_days", lambda: ["2026-01-15"])

        with pytest.raises(HTTPException, match="Day 2026-01-16 not found"):
            days_mod.get_day("2026-01-16")

    def test_returns_db_consistent_fallback_when_filesystem_missing(self, monkeypatch):
        monkeypatch.setattr(days_mod, "load_available_days", lambda: ["2026-01-15"])
        monkeypatch.setattr(days_mod, "get_day_summary", lambda *_args: {"error": "missing"})

        summary = days_mod.get_day("2026-01-15")

        assert summary.date == "2026-01-15"
        assert summary.total_files == 0
        assert summary.file_types == {}
        assert summary.total_size_kb == 0.0

    def test_validates_and_returns_parser_summary(self, monkeypatch):
        monkeypatch.setattr(days_mod, "load_available_days", lambda: ["2026-01-15"])
        monkeypatch.setattr(
            days_mod,
            "get_day_summary",
            lambda *_args: {
                "date": "2026-01-15",
                "total_files": 3,
                "file_types": {"WELLNESS": 2, "SLEEP_DATA": 1},
                "total_size_kb": 12.5,
            },
        )

        summary = days_mod.get_day("2026-01-15")
        assert summary.total_files == 3
        assert summary.file_types["WELLNESS"] == 2
