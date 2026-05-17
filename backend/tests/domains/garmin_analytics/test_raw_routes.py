"""Route coverage for canonical Garmin raw metric endpoints."""

from fastapi.testclient import TestClient
from httpx import Response

from app.main import app

client = TestClient(app)


def _response(path: str) -> Response:
    return client.get(path)


def _status(path: str) -> int:
    return _response(path).status_code


def _assert_missing_route(path: str) -> None:
    response = _response(path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def _assert_route_registered(path: str) -> None:
    response = _response(path)
    assert response.json() != {"detail": "Not Found"}, response.text


def test_sleep_raw_route_replaces_ambiguous_base_route() -> None:
    assert _status("/api/sleep/raw") == 200
    _assert_missing_route("/api/sleep")
    assert _status("/api/sleep/analysis") == 200
    assert _status("/api/sleep/daily") == 200


def test_hrv_raw_route_replaces_ambiguous_base_route() -> None:
    assert _status("/api/hrv/raw") == 200
    _assert_missing_route("/api/hrv")
    assert _status("/api/hrv/analysis") == 200
    _assert_route_registered("/api/hrv/insights")
    assert _status("/api/hrv/daily") == 200


def test_skin_temp_raw_route_replaces_ambiguous_base_route() -> None:
    assert _status("/api/skin-temp/raw") == 200
    _assert_missing_route("/api/skin-temp")
    assert _status("/api/skin-temp/daily") == 200
