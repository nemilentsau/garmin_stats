"""Shared HTTP error payload and OpenAPI response metadata."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from app.contracts.base import StrictDefaultsRequired


class ApiErrorResponse(StrictDefaultsRequired):
    """Stable JSON body returned for application-level HTTP failures."""

    detail: str


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Build FastAPI response metadata backed by the shared error contract."""
    return {
        code: {
            "model": ApiErrorResponse,
            "description": HTTPStatus(code).phrase,
        }
        for code in status_codes
    }
