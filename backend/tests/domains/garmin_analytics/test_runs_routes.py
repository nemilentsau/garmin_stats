"""Runs routes: list filtering, detail 404, series shape."""

from fastapi.testclient import TestClient

from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
)
from app.infra.sqlite import connect
from app.main import app
from tests._runs_helpers import insert_run

client = TestClient(app)


def test_list_runs_ordered_and_filtered():
    insert_run("2026-07-01", "r1")
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs", params={"from": "2026-07-05"}).json()
    assert [r["id"] for r in body["runs"]] == ["r2"]
    assert body["runs"][0]["pace_min_per_mi"] is not None


def test_list_serves_imperial_display_fields():
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs").json()
    run = body["runs"][0]
    assert "pace_min_per_km" not in run and "distance_m" not in run
    assert run["distance_mi"] == round(9695.29 / 1609.344, 2)
    assert run["pace_min_per_mi"] == round(5.24 * 1.609344, 2)


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


def test_run_detail_display_converts_metric_session_to_imperial():
    insert_run(
        "2026-07-10",
        "r2",
        lap_count=1,
        total_ascent_m=139,
        total_descent_m=100,
        avg_temperature_c=31,
        min_temperature_c=18,
        max_temperature_c=33,
        avg_speed_mps=3.5,
        max_speed_mps=4.2,
        grade_adjusted_avg_speed_mps=3.0,
        avg_vertical_oscillation_mm=88.0,
    )
    body = client.get("/api/activities/runs/r2").json()
    display = body["display"]

    assert display["distance_mi"] == round(9695.29 / 1609.344, 2)
    assert display["pace_min_per_mi"] == round(5.24 * 1.609344, 2)
    assert display["gap_min_per_mi"] == round(1000 / (3.0 * 60) * 1.609344, 2)
    assert display["avg_speed_mph"] == round(3.5 * 2.2369363, 1)
    assert display["max_speed_mph"] == round(4.2 * 2.2369363, 1)
    assert display["total_ascent_ft"] == round(139 * 3.28084, 0)
    assert display["total_descent_ft"] == round(100 * 3.28084, 0)
    assert display["avg_temperature_f"] == round(31 * 9 / 5 + 32, 1)
    assert display["min_temperature_f"] == round(18 * 9 / 5 + 32, 1)
    assert display["max_temperature_f"] == round(33 * 9 / 5 + 32, 1)
    assert display["avg_vertical_oscillation_cm"] == round(88.0 / 10, 1)

    lap_display = display["lap_display"][0]
    assert lap_display["lap_index"] == 0
    assert lap_display["distance_mi"] == round(1609.34 / 1609.344, 2)
    assert lap_display["pace_min_per_mi"] is None  # lap has no stored pace_min_per_km


def test_run_detail_display_preserves_none_for_missing_metric_fields():
    """None-preservation branch for every converter: a run with no ascent, temp,
    speed, or vertical-oscillation source data yields None display fields,
    while the always-populated distance/pace fields stay non-None."""
    insert_run("2026-07-10", "r2", lap_count=1)
    body = client.get("/api/activities/runs/r2").json()
    display = body["display"]

    assert display["distance_mi"] is not None
    assert display["pace_min_per_mi"] is not None
    assert display["gap_min_per_mi"] is None
    assert display["avg_speed_mph"] is None
    assert display["max_speed_mph"] is None
    assert display["total_ascent_ft"] is None
    assert display["total_descent_ft"] is None
    assert display["avg_temperature_f"] is None
    assert display["min_temperature_f"] is None
    assert display["max_temperature_f"] is None
    assert display["avg_vertical_oscillation_cm"] is None
    assert display["avg_ground_contact_balance_label"] is None
    assert display["avg_stance_time_pct"] is None
    assert display["avg_respiration_rate_brpm"] is None
    assert display["max_respiration_rate_brpm"] is None
    assert display["min_respiration_rate_brpm"] is None
    assert display["stamina_beginning_potential_pct"] is None
    assert display["stamina_ending_potential_pct"] is None
    assert display["stamina_min_pct"] is None

    lap_display = display["lap_display"][0]
    assert lap_display["avg_ground_contact_balance_label"] is None
    assert lap_display["avg_respiration_rate_brpm"] is None
    assert lap_display["avg_vertical_oscillation_cm"] is None


def test_run_detail_display_includes_strap_dynamics_for_strap_run():
    """Strap-run branch: a run (and its laps) with chest-strap dynamics gets a
    rendered balance label plus the respiration/stance-time pass-throughs, at
    both the session and lap-display level."""
    insert_run(
        "2026-07-05",
        "strap-run",
        lap_count=1,
        avg_ground_contact_balance_pct=49.76,
        avg_stance_time_pct=33.42,
        avg_respiration_rate_brpm=35.78,
        max_respiration_rate_brpm=45.44,
        min_respiration_rate_brpm=23.2,
        lap_avg_ground_contact_balance_pct=49.62,
        lap_avg_respiration_rate_brpm=33.42,
        lap_avg_vertical_oscillation_mm=80.6,
    )
    body = client.get("/api/activities/runs/strap-run").json()
    display = body["display"]

    assert display["avg_ground_contact_balance_label"] == "49.8% L / 50.2% R"
    assert display["avg_stance_time_pct"] == 33.42
    assert display["avg_respiration_rate_brpm"] == 35.78
    assert display["max_respiration_rate_brpm"] == 45.44
    assert display["min_respiration_rate_brpm"] == 23.2

    lap_display = display["lap_display"][0]
    assert lap_display["avg_ground_contact_balance_label"] == "49.6% L / 50.4% R"
    assert lap_display["avg_respiration_rate_brpm"] == 33.42
    assert lap_display["avg_vertical_oscillation_cm"] == round(80.6 / 10, 1)


def test_run_detail_display_includes_stamina_scalars_when_present():
    """Stamina fields are watch-level (Firstbeat), not strap-dependent — present on
    this run alongside no strap-dynamics data, unlike the strap-only fields above."""
    insert_run(
        "2026-07-10",
        "wrist-run",
        stamina_beginning_potential_pct=98,
        stamina_ending_potential_pct=77,
        stamina_min_pct=77,
    )
    body = client.get("/api/activities/runs/wrist-run").json()
    display = body["display"]

    assert display["stamina_beginning_potential_pct"] == 98
    assert display["stamina_ending_potential_pct"] == 77
    assert display["stamina_min_pct"] == 77


def test_missing_run_is_404():
    assert client.get("/api/activities/runs/nope").status_code == 404
    assert client.get("/api/activities/runs/nope/series").status_code == 404


def test_series_serves_imperial_arrays():
    insert_run("2026-07-10", "r2")
    speeds: list[float | None] = []
    speeds.extend([3.2] * 12)
    speeds.append(0.1)
    series = RunningActivitySeries(
        elapsed_s=list(range(13)),
        speed_mps=speeds,
    )
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("r2", series.model_dump_json()),
        )
        con.commit()

    body = client.get("/api/activities/runs/r2/series").json()
    assert body["series"]["elapsed_s"] == list(range(13))
    assert "pace_min_per_km" not in body
    assert body["pace_min_per_mi"][:10] == [None] * 10
    # speed 3.2 m/s → min/km = 1000/(3.2*60); min/mi = that × 1.609344
    assert round(body["pace_min_per_mi"][10], 3) == round(
        1000 / (3.2 * 60) * 1.609344, 3
    )
    assert body["pace_min_per_mi"][12] is None  # 0.1 m/s below threshold


def test_series_masks_start_and_resume_transitions_without_mutating_raw_series():
    insert_run("2026-07-10", "transition-run")
    elapsed = [*range(12), *range(100, 111)]
    count = len(elapsed)
    series = RunningActivitySeries(
        elapsed_s=elapsed,
        speed_mps=[3.2] * count,
        cadence_spm=[180.0] * count,
        step_length_mm=[1200.0] * count,
        vertical_oscillation_mm=[80.0] * count,
        vertical_ratio_pct=[7.0] * count,
        stance_time_ms=[220.0] * count,
        stance_time_balance_pct=[49.0] * count,
        stance_time_pct=[34.0] * count,
    )
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("transition-run", series.model_dump_json()),
        )
        con.commit()

    body = client.get("/api/activities/runs/transition-run/series").json()

    assert body["pace_min_per_mi"][:10] == [None] * 10
    assert body["pace_min_per_mi"][10] is not None
    assert body["pace_min_per_mi"][12:22] == [None] * 10
    assert body["pace_min_per_mi"][22] is not None
    assert body["cadence_spm"][0] is None
    assert body["step_length_m"][0] is None
    assert body["vertical_oscillation_cm"][0] is None
    assert body["vertical_ratio_pct"][0] is None
    assert body["ground_contact_time_ms"][0] is None
    assert body["ground_contact_balance_pct"][0] is None
    assert body["stance_time_pct"][0] is None
    assert body["series"]["vertical_ratio_pct"][0] == 7.0
    assert body["series"]["stance_time_ms"][0] == 220.0


def test_run_detail_uses_smoothed_profile_for_display_totals_and_preserves_fit_totals():
    insert_run(
        "2026-07-10",
        "elevation-run",
        total_ascent_m=139,
        total_descent_m=100,
    )
    distances: list[float | None] = [float(value) for value in range(0, 701, 50)]
    altitudes: list[float | None] = [
        0.0,
        0.0,
        2.0,
        4.0,
        6.0,
        8.0,
        10.0,
        10.0,
        10.0,
        8.0,
        6.0,
        4.0,
        2.0,
        0.0,
        0.0,
    ]
    series = RunningActivitySeries(
        elapsed_s=list(range(len(distances))),
        distance_m=distances,
        altitude_m=altitudes,
        lat=[40.7206] * len(distances),
        lon=[-74.0415] * len(distances),
    )
    with connect() as con:
        row = con.execute(
            "SELECT data FROM running_activity_sessions WHERE id = ?", ("elevation-run",)
        ).fetchone()
        session = RunningActivitySession.model_validate_json(row["data"]).model_copy(
            update={
                "start_lat": 40.7206,
                "start_lon": -74.0415,
                "end_lat": 40.7206,
                "end_lon": -74.0415,
            }
        )
        con.execute(
            "UPDATE running_activity_sessions SET data = ? WHERE id = ?",
            (session.model_dump_json(), "elevation-run"),
        )
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("elevation-run", series.model_dump_json()),
        )
        con.commit()

    detail = client.get("/api/activities/runs/elevation-run").json()

    assert detail["session"]["total_ascent_m"] == 139
    assert detail["session"]["total_descent_m"] == 100
    assert detail["display"]["total_ascent_ft"] == round(10.0 * 3.28084, 0)
    assert detail["display"]["total_descent_ft"] == round(10.0 * 3.28084, 0)


def test_series_strap_dynamics_arrays_absent_for_wrist_run():
    """Wrist-only branch: a run with no strap-dynamics series data yields
    empty arrays inside the embedded series (the model's `[]` default), not a
    3-slot None-filled array — the frontend's `hasData` gate treats both the
    same, but empty is what the wrist-only ingest actually stores."""
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs/r2/series").json()
    assert body["series"]["stance_time_balance_pct"] == []
    assert body["series"]["respiration_rate_brpm"] == []
    assert body["series"]["stance_time_pct"] == []
    # Movement-dependent display copies are empty when the raw source is empty.
    assert "stance_time_balance_pct" not in body
    assert "respiration_rate_brpm" not in body
    assert body["ground_contact_balance_pct"] == []
    assert body["stance_time_pct"] == []


def test_series_passes_through_strap_dynamics_arrays_for_strap_run():
    """Strap-run branch: balance/respiration/stance-time arrays live inside
    the embedded series, unchanged (native units, no imperial conversion) and
    preserve None gaps."""
    insert_run(
        "2026-07-05",
        "strap-run",
        stance_time_balance_pct=[49.09, None, 49.46],
        respiration_rate_brpm=[23.2, 23.2, None],
        stance_time_pct=[35.25, 35.0, None],
    )
    body = client.get("/api/activities/runs/strap-run/series").json()
    assert body["series"]["stance_time_balance_pct"] == [49.09, None, 49.46]
    assert body["series"]["respiration_rate_brpm"] == [23.2, 23.2, None]
    assert body["series"]["stance_time_pct"] == [35.25, 35.0, None]
    # The new top-level chart copies are masked; the canonical arrays above are not.
    assert "stance_time_balance_pct" not in body
    assert "respiration_rate_brpm" not in body
    assert body["ground_contact_balance_pct"] == [None, None, None]
    assert body["stance_time_pct"] == [None, None, None]


def test_series_passes_through_stamina_and_performance_condition_arrays():
    """Stamina/potential/PC arrays live only inside the embedded series (no top-level
    duplicate — the strap-dynamics duplication mistake reverted in commit 59abb86)."""
    insert_run(
        "2026-07-10",
        "r2",
        stamina_pct=[98, 90, 77],
        stamina_potential_pct=[98, 95, 77],
        performance_condition=[None, 1, 2],
    )
    body = client.get("/api/activities/runs/r2/series").json()
    assert body["series"]["stamina_pct"] == [98, 90, 77]
    assert body["series"]["stamina_potential_pct"] == [98, 95, 77]
    assert body["series"]["performance_condition"] == [None, 1, 2]
    assert "stamina_pct" not in body
    assert "stamina_potential_pct" not in body
    assert "performance_condition" not in body


def test_series_stamina_arrays_absent_when_not_populated():
    """A run with no stamina series data yields empty arrays inside the embedded
    series (the model's `[]` default), matching the wrist-only-strap-dynamics pattern."""
    insert_run("2026-07-10", "r2")
    body = client.get("/api/activities/runs/r2/series").json()
    assert body["series"]["stamina_pct"] == []
    assert body["series"]["stamina_potential_pct"] == []
    assert body["series"]["performance_condition"] == []


def test_series_pace_at_exact_threshold_is_computed_and_missing_speed_is_null():
    insert_run("2026-07-10", "r2")
    series = RunningActivitySeries(
        elapsed_s=list(range(13)),
        speed_mps=[3.0] * 10 + [0.5, 0.4, None],
    )
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("r2", series.model_dump_json()),
        )
        con.commit()

    body = client.get("/api/activities/runs/r2/series").json()

    assert round(body["pace_min_per_mi"][10], 3) == round(
        1000 / (0.5 * 60) * 1.609344, 3
    )
    assert body["pace_min_per_mi"][11] is None  # 0.4 m/s below the 0.5 threshold
    assert body["pace_min_per_mi"][12] is None  # missing speed sample


def test_series_converts_altitude_temperature_distance_arrays_with_null_preserved():
    insert_run("2026-07-10", "r2")
    series = RunningActivitySeries(
        elapsed_s=[0, 1, 2],
        altitude_m=[100.0, None, 120.0],
        temperature_c=[20.0, None, 22.0],
        distance_m=[0.0, None, 50.0],
    )
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("r2", series.model_dump_json()),
        )
        con.commit()

    body = client.get("/api/activities/runs/r2/series").json()

    assert body["altitude_ft"] == [round(100.0 * 3.28084, 0), None, round(120.0 * 3.28084, 0)]
    assert body["temperature_f"] == [
        round(20.0 * 9 / 5 + 32, 1),
        None,
        round(22.0 * 9 / 5 + 32, 1),
    ]
    assert body["distance_mi"] == [round(0.0 / 1609.344, 2), None, round(50.0 / 1609.344, 2)]


def test_series_converts_running_dynamics_to_garmin_display_units():
    insert_run("2026-07-10", "r2")
    series = RunningActivitySeries(
        elapsed_s=list(range(13)),
        step_length_mm=[1100.0] * 10 + [1200.0, None, 980.0],
        vertical_oscillation_mm=[80.0] * 10 + [88.0, None, 75.0],
    )
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            ("r2", series.model_dump_json()),
        )
        con.commit()

    body = client.get("/api/activities/runs/r2/series").json()

    assert body["step_length_m"][:10] == [None] * 10
    assert body["vertical_oscillation_cm"][:10] == [None] * 10
    assert body["step_length_m"][10:] == [1.2, None, 0.98]
    assert body["vertical_oscillation_cm"][10:] == [8.8, None, 7.5]
