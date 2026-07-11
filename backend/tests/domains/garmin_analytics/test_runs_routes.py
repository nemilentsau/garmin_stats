"""Runs routes: list filtering, detail 404, series shape."""

from fastapi.testclient import TestClient

from app.domains.garmin_health.contracts import RunningActivityLap, RunningActivitySeries
from app.infra.sqlite import connect
from app.main import app
from tests._runs_helpers import insert_run

client = TestClient(app)


def test_list_runs_ordered_and_filtered():
    insert_run("2026-07-01", "r1")
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs", params={"from": "2026-07-05"}).json()
    assert [r["id"] for r in body["runs"]] == ["r2"]
    assert body["runs"][0]["pace_min_per_km"] is not None


def test_list_runs_newest_first_without_date_filter():
    insert_run("2026-07-01", "r1")
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs").json()
    assert [r["id"] for r in body["runs"]] == ["r2", "r1"]


def test_list_runs_from_and_to_are_inclusive_boundaries():
    insert_run("2026-07-01", "r1")
    insert_run("2026-07-05", "r2")
    insert_run("2026-07-10", "r3")
    body = client.get(
        "/api/activities/runs",
        params={"from": "2026-07-01", "to": "2026-07-05"},
    ).json()
    assert [r["id"] for r in body["runs"]] == ["r2", "r1"]


def test_list_runs_excludes_runs_outside_the_window():
    insert_run("2026-06-30", "before")
    insert_run("2026-07-05", "inside")
    insert_run("2026-07-11", "after")
    body = client.get(
        "/api/activities/runs",
        params={"from": "2026-07-01", "to": "2026-07-10"},
    ).json()
    assert [r["id"] for r in body["runs"]] == ["inside"]


def test_run_detail_includes_session_and_laps():
    insert_run("2026-07-10", "r2", lap_count=2)
    body = client.get("/api/activities/runs/r2").json()
    assert body["session"]["id"] == "r2"
    assert len(body["laps"]) == 2


def test_run_detail_laps_are_ordered_by_lap_index_not_insertion_order():
    insert_run("2026-07-10", "r2")
    with connect() as con:
        for lap_index in (2, 0, 1):
            lap = RunningActivityLap(lap_index=lap_index, distance_m=1000.0 * (lap_index + 1))
            con.execute(
                "INSERT OR REPLACE INTO running_activity_laps (session_id, lap_index, data)"
                " VALUES (?, ?, ?)",
                ("r2", lap_index, lap.model_dump_json()),
            )
        con.commit()

    body = client.get("/api/activities/runs/r2").json()

    assert [lap["lap_index"] for lap in body["laps"]] == [0, 1, 2]


def test_missing_run_is_404():
    assert client.get("/api/activities/runs/nope").status_code == 404
    assert client.get("/api/activities/runs/nope/series").status_code == 404


def test_series_returns_parallel_arrays_with_backend_pace():
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs/r2/series").json()
    assert body["series"]["elapsed_s"] == [0, 1, 2]
    # speed 3.2 m/s → 1000/(3.2*60); zero-ish speed → null pace
    assert round(body["pace_min_per_km"][0], 3) == round(1000 / (3.2 * 60), 3)
    assert body["pace_min_per_km"][2] is None


def test_series_pace_at_exact_threshold_is_computed_and_missing_speed_is_null():
    insert_run("2026-07-10", "r2")
    series = RunningActivitySeries(
        elapsed_s=[0, 1, 2],
        speed_mps=[0.5, 0.4, None],
    )
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("r2", series.model_dump_json()),
        )
        con.commit()

    body = client.get("/api/activities/runs/r2/series").json()

    assert round(body["pace_min_per_km"][0], 3) == round(1000 / (0.5 * 60), 3)
    assert body["pace_min_per_km"][1] is None
    assert body["pace_min_per_km"][2] is None
