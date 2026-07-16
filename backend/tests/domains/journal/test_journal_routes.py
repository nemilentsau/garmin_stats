"""Journal HTTP date-boundary tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_journal_date_filter_rejects_malformed_date():
    response = client.get("/api/checkins", params={"date": "not-a-date"})

    assert response.status_code == 422
