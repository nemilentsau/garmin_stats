"""Running-activity parser tests: extraction rules, unit policy, hr_source."""

import json
from datetime import UTC, datetime, timedelta

import app.domains.garmin_health.infra.fit_parser.activities as activities_mod
from app.domains.garmin_health.infra.fit_parser.activities import (
    discover_running_activity_files,
    parse_running_activity,
)
from app.domains.garmin_health.infra.fit_parser.activity_extractors import (
    _derive_utc_offset,
    _detect_hr_source,
    _extract_run_laps,
    _extract_run_series,
    _extract_run_session,
)

START = datetime(2026, 7, 10, 14, 57, 26, tzinfo=UTC)

SESSION_MSG = {
    "start_time": START,
    "timestamp": START,
    "total_elapsed_time": 3303.155,
    "total_timer_time": 3050.674,
    "total_distance": 9695.29,
    "enhanced_avg_speed": 3.178,
    "enhanced_max_speed": 4.068,
    "total_ascent": 139,
    "total_descent": 133,
    "avg_heart_rate": 139,
    "max_heart_rate": 157,
    "avg_power": 417,
    "max_power": 649,
    "normalized_power": 422,
    "total_work": 1277397,
    "avg_running_cadence": 87,
    "avg_fractional_cadence": 0.71875,
    "max_running_cadence": 97,
    "max_fractional_cadence": 0.0,
    "avg_stance_time": 252.1,
    "avg_stance_time_balance": 49.76,
    "avg_stance_time_percent": 33.42,
    "enhanced_avg_respiration_rate": 35.78,
    "enhanced_max_respiration_rate": 45.44,
    "enhanced_min_respiration_rate": 23.2,
    "avg_step_length": 1067.2,
    "avg_vertical_oscillation": 80.5,
    "avg_vertical_ratio": 7.55,
    "avg_temperature": 31,
    "min_temperature": 29,
    "max_temperature": 32,
    "total_calories": 822,
    "total_strides": 4539,
    "total_training_effect": 3.4,
    "total_anaerobic_training_effect": 0.0,
    "training_load_peak": 126.01954650878906,
    "sport": "running",
    "sub_sport": "generic",
    "sport_profile_name": "Run",
    "num_laps": 7,
    "start_position_lat": 485817669,
    "start_position_long": -883343073,
    "end_position_lat": 485816764,
    "end_position_long": -883338322,
}

SIDECAR = {
    "activityId": 23548921459,
    "activityName": "Jersey City Running",
    "startTimeGMT": "2026-07-10 14:57:26",
    "startTimeLocal": "2026-07-10 10:57:26",
    "movingDuration": 3008.5280151367188,
    "vO2MaxValue": 52.0,
    "avgGradeAdjustedSpeed": 3.174999952316284,
    "aerobicTrainingEffectMessage": "IMPROVING_AEROBIC_BASE_8",
    "anaerobicTrainingEffectMessage": "NO_ANAEROBIC_BENEFIT_0",
    "trainingEffectLabel": "AEROBIC_BASE",
    "differenceBodyBattery": -7,
    "steps": 9078,
    "locationName": "Jersey City",
    "moderateIntensityMinutes": 1,
    "vigorousIntensityMinutes": 53,
}

STRAP_DEVICE = {
    "source_type": "bluetooth_low_energy",
    "ble_device_type": "heart_rate",
    "manufacturer": "garmin",
    "serial_number": 3616916681,
    "battery_status": "good",
}
LOCAL_DEVICE = {"source_type": "local", "device_type": 4, "manufacturer": "garmin"}

ZONE_MSGS = [
    {
        "reference_mesg": "session",
        "reference_index": 0,
        "time_in_hr_zone": [26.937, 56.818, 497.946, 1819.387, 649.458, 0.0, 0.0],
        "hr_zone_high_boundary": [95, 111, 131, 149, 162, 182],
        "time_in_power_zone": [108.648, 515.179, 1207.221, 866.573, 295.922, 57.003, 0.0, 0.0],
        "power_zone_high_boundary": [316, 387, 434, 483, 554, 4000, None, None],
        "functional_threshold_power": 483,
        "threshold_heart_rate": 161,
        "max_heart_rate": 182,
    },
    {"reference_mesg": "lap", "reference_index": 0, "time_in_hr_zone": [1.0]},
]


def _messages(devices=(LOCAL_DEVICE,)):
    return {
        "session_mesgs": [SESSION_MSG],
        "device_info_mesgs": list(devices),
        "time_in_zone_mesgs": ZONE_MSGS,
    }


class TestUtcOffset:
    def test_offset_from_sidecar_gmt_vs_local(self):
        assert _derive_utc_offset(SIDECAR, {}) == -4.0

    def test_offset_falls_back_to_activity_mesg_local_timestamp(self):
        messages = {
            "activity_mesgs": [
                {
                    "timestamp": START,
                    "local_timestamp": datetime(2026, 7, 10, 10, 57, 26),
                }
            ]
        }
        assert _derive_utc_offset(None, messages) == -4.0

    def test_offset_none_when_no_source(self):
        assert _derive_utc_offset(None, {}) is None


class TestHrSource:
    def test_strap_detected_from_ble_heart_rate_device(self):
        source, serial, battery = _detect_hr_source(_messages((LOCAL_DEVICE, STRAP_DEVICE)), True)
        assert (source, serial, battery) == ("strap", "3616916681", "good")

    def test_wrist_when_hr_present_without_external_device(self):
        source, serial, battery = _detect_hr_source(_messages(), True)
        assert (source, serial, battery) == ("wrist", None, None)

    def test_none_when_no_hr(self):
        assert _detect_hr_source(_messages(), False) == (None, None, None)


class TestSessionExtraction:
    def test_strips_only_trailing_none_in_zone_lists(self):
        """Non-trailing None must be preserved; only trailing Nones stripped."""
        zone_msgs = [
            {
                "reference_mesg": "session",
                "time_in_hr_zone": [10.0, None, 20.0, None, None],
                "hr_zone_high_boundary": [100, None, 150, None, None],
                "time_in_power_zone": None,
                "power_zone_high_boundary": None,
            }
        ]
        messages = {
            "session_mesgs": [SESSION_MSG],
            "device_info_mesgs": [LOCAL_DEVICE],
            "time_in_zone_mesgs": zone_msgs,
        }
        session = _extract_run_session(messages, None, "test.fit")
        # Trailing Nones stripped, non-trailing None preserved
        assert session.time_in_zones is not None
        assert session.time_in_zones.time_in_hr_zone_s == [10.0, None, 20.0]
        assert session.time_in_zones.hr_zone_high_boundary_bpm == [100, None, 150]

    def test_merges_fit_and_sidecar_with_unit_policy(self):
        session = _extract_run_session(
            _messages(), SIDECAR, "2026-07-10/105726_running_generic.fit"
        )
        assert session.id == "23548921459"
        assert session.activity_id == "23548921459"
        assert session.session_date == "2026-07-10"
        assert session.start_time_local == "2026-07-10T10:57:26"
        assert session.utc_offset_hours == -4.0
        assert session.avg_cadence_spm == 175.4375  # (87 + 0.71875) * 2
        assert session.max_cadence_spm == 194.0
        assert session.pace_min_per_km == round(3050.674 / 60 / 9.69529, 2)
        assert session.moving_time_s == 3008.5280151367188
        assert session.vo2max == 52.0
        assert session.grade_adjusted_avg_speed_mps == 3.174999952316284
        assert session.start_lat == round(485817669 * (180 / 2**31), 7)
        assert session.time_in_zones is not None
        assert session.time_in_zones.time_in_hr_zone_s[3] == 1819.387
        assert session.time_in_zones.power_zone_high_boundary_w == [316, 387, 434, 483, 554, 4000]
        assert session.has_heart_rate is True
        assert session.has_power is True
        assert session.has_running_dynamics is True
        # HR source integration: wrist optical (no external strap)
        assert session.hr_source == "wrist"
        assert session.hr_strap_serial is None
        assert session.hr_strap_battery is None
        # Body battery delta from sidecar
        assert session.body_battery_delta == -7

    def test_no_sidecar_derives_id_from_source_file_and_keeps_fit_fields(self):
        session = _extract_run_session(_messages(), None, "2026-07-10/105726_running_generic.fit")
        assert session.id.startswith("file-")
        assert "/" not in session.id
        assert session.id == _extract_run_session(
            _messages(), None, "2026-07-10/105726_running_generic.fit"
        ).id
        assert session.id != _extract_run_session(
            _messages(), None, "2026-07-11/105726_running_generic.fit"
        ).id
        assert session.activity_id is None
        assert session.vo2max is None
        # no offset source → start time stays UTC-naive and is flagged as such
        assert session.utc_offset_hours is None
        assert session.start_time_local == "2026-07-10T14:57:26"

    def test_missing_optional_fields_stay_none(self):
        bare = {"session_mesgs": [{"start_time": START, "timestamp": START, "sport": "running"}]}
        session = _extract_run_session(bare, None, "2026-07-10/x_running_generic.fit")
        assert session.avg_heart_rate_bpm is None
        assert session.has_heart_rate is False
        assert session.time_in_zones is None

    def test_strap_dynamics_fields_mapped_from_fit_to_session(self):
        """Session strap fields extracted and has_strap_dynamics set when balance is present."""
        session = _extract_run_session(
            _messages(), SIDECAR, "2026-07-10/105726_running_generic.fit"
        )
        assert session.avg_ground_contact_balance_pct == 49.76
        assert session.avg_stance_time_pct == 33.42
        assert session.avg_respiration_rate_brpm == 35.78
        assert session.max_respiration_rate_brpm == 45.44
        assert session.min_respiration_rate_brpm == 23.2
        assert session.has_strap_dynamics is True

    def test_wrist_style_session_lacks_strap_dynamics(self):
        """Wrist-style session (no balance) → all strap fields None + flag False."""
        bare = {
            "session_mesgs": [
                {
                    "start_time": START,
                    "timestamp": START,
                    "sport": "running",
                    "avg_heart_rate": 140,
                }
            ]
        }
        session = _extract_run_session(bare, None, "2026-07-10/x_running_generic.fit")
        assert session.avg_ground_contact_balance_pct is None
        assert session.avg_stance_time_pct is None
        assert session.avg_respiration_rate_brpm is None
        assert session.max_respiration_rate_brpm is None
        assert session.min_respiration_rate_brpm is None
        assert session.has_strap_dynamics is False


def _record(
    ts_offset_s,
    *,
    stamina: int | None = 92,
    stamina_potential: int | None = 92,
    performance_condition: int | None = 1,
    **overrides,
):
    """Base record dict. `stamina`/`stamina_potential`/`performance_condition` map to
    the undocumented numeric FIT keys 138/137/90 (the SDK exposes these as int dict
    keys, not named fields) — kept as named params since int keys can't be passed
    via `**overrides` kwargs."""
    base = {
        "timestamp": START + timedelta(seconds=ts_offset_s),
        "distance": 0.48,
        "enhanced_speed": 3.1,
        "enhanced_altitude": -21.6,
        "heart_rate": 140,
        "cadence": 88,
        "fractional_cadence": 0.5,
        "power": 410,
        "step_length": 1067.0,
        "vertical_oscillation": 80.1,
        "vertical_ratio": 7.5,
        "stance_time": 252.0,
        "stance_time_balance": 49.09,
        "enhanced_respiration_rate": 23.2,
        "stance_time_percent": 35.25,
        "temperature": 31,
        "position_lat": 485817669,
        "position_long": -883343073,
        138: stamina,
        137: stamina_potential,
        90: performance_condition,
    }
    base.update(overrides)
    return base


class TestSeriesExtraction:
    def test_column_arrays_preserve_positional_nulls_and_units(self):
        messages = {
            "record_mesgs": [
                _record(0),
                _record(
                    1,
                    stance_time=None,
                    step_length=None,
                    heart_rate=None,
                    stance_time_balance=None,
                    enhanced_respiration_rate=None,
                    stance_time_percent=None,
                ),
            ],
            "split_mesgs": [
                {
                    "split_type": "rwd_run",
                    "start_time": START,
                    "end_time": START + timedelta(seconds=90),
                },
                {
                    "split_type": "rwd_stand",
                    "start_time": START + timedelta(seconds=90),
                    "end_time": START + timedelta(seconds=100),
                },
                {"split_type": "interval_active", "start_time": START, "end_time": START},
            ],
        }
        series = _extract_run_series(messages)
        assert series.elapsed_s == [0, 1]
        assert series.cadence_spm == [177.0, 177.0]  # (88 + 0.5) * 2
        assert series.heart_rate_bpm == [140, None]
        assert series.stance_time_ms == [252.0, None]
        assert series.stance_time_balance_pct == [49.09, None]
        assert series.respiration_rate_brpm == [23.2, None]
        assert series.stance_time_pct == [35.25, None]
        assert series.lat[0] == round(485817669 * (180 / 2**31), 7)
        assert [s.span_type for s in series.run_walk_spans] == ["run", "stand"]
        assert series.run_walk_spans[0].end_s == 90.0

    def test_stamina_and_performance_condition_mapped_with_positional_nulls(self):
        """137 = stamina potential, 138 = stamina, 90 = performance condition
        (undocumented numeric FIT keys the SDK exposes as int dict keys). Field 90
        is sparse — Garmin baselines for the first ~6-8min before emitting it — so
        the leading record (no PC yet) pins a leading None distinct from the dense
        137/138 channels, which are populated from the first record."""
        messages = {
            "record_mesgs": [
                _record(0, stamina=92, stamina_potential=98, performance_condition=None),
                _record(1, stamina=90, stamina_potential=97, performance_condition=1),
                _record(2, stamina=None, stamina_potential=None, performance_condition=None),
            ],
        }
        series = _extract_run_series(messages)
        assert series.stamina_pct == [92, 90, None]
        assert series.stamina_potential_pct == [98, 97, None]
        assert series.performance_condition == [None, 1, None]

    def test_empty_records_yield_empty_series(self):
        series = _extract_run_series({})
        assert series.elapsed_s == []
        assert series.run_walk_spans == []

    def test_span_dropped_when_mapped_split_type_missing_timestamp(self):
        """Spans with missing start_time or end_time are dropped; only rwd_* with both kept."""
        messages = {
            "record_mesgs": [_record(0)],
            "split_mesgs": [
                {
                    "split_type": "rwd_walk",
                    "start_time": None,
                    "end_time": START + timedelta(seconds=30),
                },
                {
                    "split_type": "rwd_run",
                    "start_time": START + timedelta(seconds=30),
                    "end_time": START + timedelta(seconds=60),
                },
            ],
        }
        series = _extract_run_series(messages)
        assert len(series.run_walk_spans) == 1
        assert series.run_walk_spans[0].span_type == "run"

    def test_wrist_style_series_has_strap_fields_empty_and_none(self):
        """Wrist-style records (no strap fields) → strap arrays hold positional Nones."""
        def _wrist_record(ts_offset_s):
            """Record without strap fields."""
            return {
                "timestamp": START + timedelta(seconds=ts_offset_s),
                "distance": 0.48,
                "enhanced_speed": 3.1,
                "heart_rate": 140,
            }

        messages = {
            "record_mesgs": [_wrist_record(0), _wrist_record(1)],
            "split_mesgs": [],
        }
        series = _extract_run_series(messages)
        assert series.elapsed_s == [0, 1]
        assert series.stance_time_balance_pct == [None, None]
        assert series.respiration_rate_brpm == [None, None]
        assert series.stance_time_pct == [None, None]
        assert series.stamina_pct == [None, None]
        assert series.stamina_potential_pct == [None, None]
        assert series.performance_condition == [None, None]


class TestLapExtraction:
    def test_laps_carry_dynamics_and_pace(self):
        messages = {
            "session_mesgs": [SESSION_MSG],
            "lap_mesgs": [
                {
                    "message_index": 0,
                    "start_time": START,
                    "total_timer_time": 542.718,
                    "total_elapsed_time": 584.572,
                    "total_distance": 1609.34,
                    "enhanced_avg_speed": 2.965,
                    "enhanced_max_speed": 3.368,
                    "avg_heart_rate": 122,
                    "max_heart_rate": 143,
                    "avg_power": 383,
                    "max_power": 470,
                    "normalized_power": 395,
                    "avg_running_cadence": 82,
                    "avg_fractional_cadence": 0.0859375,
                    "max_running_cadence": 91,
                    "max_fractional_cadence": 0.0,
                    "avg_stance_time": 258.8,
                    "avg_step_length": 1064.1,
                    "avg_vertical_oscillation": 82.2,
                    "avg_vertical_ratio": 7.77,
                    "total_ascent": 2,
                    "total_descent": 1,
                    "total_calories": 132,
                    "intensity": "interval",
                    "lap_trigger": "distance",
                }
            ],
        }
        laps = _extract_run_laps(messages)
        assert len(laps) == 1
        lap = laps[0]
        assert lap.lap_index == 0
        assert lap.start_s == 0.0
        assert lap.pace_min_per_km == round(542.718 / 60 / 1.60934, 2)
        assert lap.avg_cadence_spm == (82 + 0.0859375) * 2
        assert lap.avg_ground_contact_time_ms == 258.8

    def test_lap_message_index_fallback_to_enumerate(self):
        """Lap without message_index uses enumerate index as lap_index."""
        messages = {
            "session_mesgs": [SESSION_MSG],
            "lap_mesgs": [
                {
                    "start_time": START,
                    "total_timer_time": 500.0,
                },
                {
                    "start_time": START + timedelta(seconds=500),
                    "total_timer_time": 300.0,
                },
            ],
        }
        laps = _extract_run_laps(messages)
        assert len(laps) == 2
        assert laps[0].lap_index == 0
        assert laps[1].lap_index == 1

    def test_lap_strap_dynamics_fields_mapped(self):
        """Lap strap fields extracted from FIT lap message."""
        messages = {
            "session_mesgs": [SESSION_MSG],
            "lap_mesgs": [
                {
                    "message_index": 0,
                    "start_time": START,
                    "total_timer_time": 542.718,
                    "total_elapsed_time": 584.572,
                    "total_distance": 1609.34,
                    "enhanced_avg_speed": 2.965,
                    "enhanced_max_speed": 3.368,
                    "avg_heart_rate": 122,
                    "max_heart_rate": 143,
                    "avg_power": 383,
                    "max_power": 470,
                    "normalized_power": 395,
                    "avg_running_cadence": 82,
                    "avg_fractional_cadence": 0.0859375,
                    "max_running_cadence": 91,
                    "max_fractional_cadence": 0.0,
                    "avg_stance_time": 258.8,
                    "avg_stance_time_balance": 50.5,
                    "avg_stance_time_percent": 34.2,
                    "enhanced_avg_respiration_rate": 34.5,
                    "enhanced_max_respiration_rate": 44.0,
                    "avg_step_length": 1064.1,
                    "avg_vertical_oscillation": 82.2,
                    "avg_vertical_ratio": 7.77,
                    "total_ascent": 2,
                    "total_descent": 1,
                    "total_calories": 132,
                    "intensity": "interval",
                    "lap_trigger": "distance",
                }
            ],
        }
        laps = _extract_run_laps(messages)
        assert len(laps) == 1
        lap = laps[0]
        assert lap.avg_ground_contact_balance_pct == 50.5
        assert lap.avg_stance_time_pct == 34.2
        assert lap.avg_respiration_rate_brpm == 34.5
        assert lap.max_respiration_rate_brpm == 44.0


def _write_activity_pair(activities_dir, day, stem, sidecar=SIDECAR):
    day_dir = activities_dir / day
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"{stem}.fit").write_bytes(b"fake-fit")
    if sidecar is not None:
        (day_dir / f"{stem}.json").write_text(json.dumps(sidecar))
    return day_dir / f"{stem}.fit"


FULL_MESSAGES = {
    "session_mesgs": [SESSION_MSG],
    "device_info_mesgs": [LOCAL_DEVICE, STRAP_DEVICE],
    "time_in_zone_mesgs": ZONE_MSGS,
    "lap_mesgs": [],
    "record_mesgs": [_record(0), _record(1)],
    "split_mesgs": [],
}


class TestDiscoveryAndComposition:
    def test_discovery_selects_only_running_fits(self, tmp_path):
        _write_activity_pair(tmp_path, "2026-07-10", "105726_running_generic")
        _write_activity_pair(tmp_path, "2026-07-09", "061913_training_strength_training")
        _write_activity_pair(tmp_path, "2026-07-08", "070000_running_trail")
        files = discover_running_activity_files(tmp_path)
        assert [f.name for f in files] == ["070000_running_trail.fit", "105726_running_generic.fit"]

    def test_discovery_excludes_generated_multi_fit_parts(self, tmp_path):
        _write_activity_pair(tmp_path, "2026-07-10", "105726_running_generic")
        _write_activity_pair(
            tmp_path,
            "2026-07-10",
            "105726_running_generic_part2",
            sidecar=None,
        )

        files = discover_running_activity_files(tmp_path)

        assert [file.name for file in files] == ["105726_running_generic.fit"]

    def test_parse_composes_session_laps_series_and_counts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(activities_mod, "decode_fit_file", lambda _: FULL_MESSAGES)
        fit = _write_activity_pair(tmp_path, "2026-07-10", "105726_running_generic")
        data = parse_running_activity(fit, tmp_path)
        assert data.session.source_file == "2026-07-10/105726_running_generic.fit"
        assert data.session.record_count == 2
        assert data.session.lap_count == 0
        assert data.session.has_gps_trace is True
        assert data.session.hr_source == "strap"
        assert data.series.elapsed_s == [0, 1]

    def test_parse_derives_stamina_session_scalars_from_series(self, tmp_path, monkeypatch):
        """Beginning/Ending Potential = first/last non-null of field 137; Min Stamina =
        min non-null of field 138 — matches Connect's Stats-panel Stamina group."""
        messages = {
            **FULL_MESSAGES,
            "record_mesgs": [
                _record(0, stamina=92, stamina_potential=98, performance_condition=None),
                _record(1, stamina=65, stamina_potential=90, performance_condition=1),
                _record(2, stamina=70, stamina_potential=65, performance_condition=2),
            ],
        }
        monkeypatch.setattr(activities_mod, "decode_fit_file", lambda _: messages)
        fit = _write_activity_pair(tmp_path, "2026-07-10", "105726_running_generic")
        data = parse_running_activity(fit, tmp_path)
        assert data.session.stamina_beginning_potential_pct == 98
        assert data.session.stamina_ending_potential_pct == 65
        assert data.session.stamina_min_pct == 65

    def test_parse_stamina_scalars_none_when_series_entirely_null(self, tmp_path, monkeypatch):
        """Old watch firmware without stamina channels: None-safe, not KeyError/min()-on-empty."""
        messages = {
            **FULL_MESSAGES,
            "record_mesgs": [
                _record(0, stamina=None, stamina_potential=None, performance_condition=None),
                _record(1, stamina=None, stamina_potential=None, performance_condition=None),
            ],
        }
        monkeypatch.setattr(activities_mod, "decode_fit_file", lambda _: messages)
        fit = _write_activity_pair(tmp_path, "2026-07-10", "105726_running_generic")
        data = parse_running_activity(fit, tmp_path)
        assert data.session.stamina_beginning_potential_pct is None
        assert data.session.stamina_ending_potential_pct is None
        assert data.session.stamina_min_pct is None

    def test_missing_activities_dir_returns_empty_list(self, tmp_path):
        files = discover_running_activity_files(tmp_path / "does_not_exist")
        assert files == []

    def test_unreadable_sidecar_warns_and_parses_with_sidecar_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(activities_mod, "decode_fit_file", lambda _: FULL_MESSAGES)
        fit = _write_activity_pair(tmp_path, "2026-07-10", "105726_running_generic")
        # Overwrite sidecar with invalid JSON
        day_dir = tmp_path / "2026-07-10"
        (day_dir / "105726_running_generic.json").write_text("{not json")

        data = parse_running_activity(fit, tmp_path)

        # Parse succeeds despite invalid sidecar
        assert data.session is not None
        # Sidecar-derived fields are None
        assert data.session.activity_id is None
        assert data.session.id.startswith("file-")
        assert "/" not in data.session.id
        # Sidecar-independent fields from FIT are intact
        assert data.session.session_date == "2026-07-10"
        assert data.session.avg_heart_rate_bpm == 139
        assert data.series.elapsed_s == [0, 1]
