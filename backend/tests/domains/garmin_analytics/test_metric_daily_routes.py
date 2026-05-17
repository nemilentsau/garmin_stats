"""Route coverage for metric-scoped daily Garmin analytics endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get(path: str) -> dict:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_heart_rate_daily_matches_daily_aggregates_subset() -> None:
    full = _get("/api/daily-aggregates")
    scoped = _get("/api/heart-rate/daily")

    assert scoped["days"] == full["days"]
    assert scoped["daily"] == [
        {
            "date": row["date"],
            "utc_offset_hours": row["utc_offset_hours"],
            "heart_rate": row["heart_rate"],
        }
        for row in full["daily"]
    ]
    assert scoped["period_windows"] == {
        label: summary["heart_rate"]
        for label, summary in full["period_windows"].items()
    }


def test_hrv_daily_matches_daily_aggregates_subset() -> None:
    full = _get("/api/daily-aggregates")
    scoped = _get("/api/hrv/daily")

    assert scoped["days"] == full["days"]
    assert scoped["daily"] == [
        {
            "date": row["date"],
            "utc_offset_hours": row["utc_offset_hours"],
            "hrv": row["hrv"],
        }
        for row in full["daily"]
    ]
    assert scoped["period_windows"] == {
        label: summary["hrv"]
        for label, summary in full["period_windows"].items()
    }


def test_sleep_daily_matches_daily_aggregates_subset() -> None:
    full = _get("/api/daily-aggregates")
    scoped = _get("/api/sleep/daily")

    assert scoped["days"] == full["days"]
    assert scoped["daily"] == [
        {
            "date": row["date"],
            "utc_offset_hours": row["utc_offset_hours"],
            "sleep": row["sleep"],
        }
        for row in full["daily"]
    ]
    assert scoped["period_windows"] == {
        label: summary["sleep"]
        for label, summary in full["period_windows"].items()
    }


def test_scalar_metric_daily_endpoints_match_daily_aggregates_subsets() -> None:
    full = _get("/api/daily-aggregates")
    cases = [
        ("/api/stress/daily", "stress"),
        ("/api/respiration/daily", "respiration"),
        ("/api/pulse-ox/daily", "spo2"),
        ("/api/skin-temp/daily", "skin_temp"),
        ("/api/body-battery/daily", "body_battery"),
    ]

    for path, field in cases:
        scoped = _get(path)
        assert scoped["days"] == full["days"]
        assert scoped["daily"] == [
            {
                "date": row["date"],
                "utc_offset_hours": row["utc_offset_hours"],
                field: row[field],
            }
            for row in full["daily"]
        ]
        assert scoped["period_windows"] == {
            label: summary[field]
            for label, summary in full["period_windows"].items()
        }
