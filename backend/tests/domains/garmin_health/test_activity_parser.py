"""Running-activity parser tests: extraction rules, unit policy, hr_source."""

from datetime import UTC, datetime

from app.domains.garmin_health.infra.fit_parser.activity_extractors import (
    _derive_utc_offset,
    _detect_hr_source,
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
        assert session.id == "file:2026-07-10/105726_running_generic"
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
