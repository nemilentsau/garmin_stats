from app.domains.garmin_analytics.domain.run_display import (
    active_running_display_mask,
    apply_display_mask,
    detrend_closed_loop_elevation,
    elevation_gain_loss_m,
    smooth_elevation_by_distance,
    zone_display_rows,
)
from app.domains.garmin_health.contracts import RunWalkSpan


def test_start_transition_masks_first_ten_seconds_only():
    elapsed = list(range(12))

    mask = active_running_display_mask(elapsed, [])

    assert mask[:10] == [False] * 10
    assert mask[10:] == [True, True]


def test_resume_transition_masks_first_ten_seconds_after_record_gap():
    elapsed = [*range(12), *range(100, 112)]

    mask = active_running_display_mask(elapsed, [])

    assert mask[10:12] == [True, True]
    assert mask[12:22] == [False] * 10
    assert mask[22:] == [True, True]


def test_walk_and_stand_spans_are_excluded_from_running_display():
    elapsed = list(range(20))
    spans = [
        RunWalkSpan(span_type="walk", start_s=11, end_s=12),
        RunWalkSpan(span_type="stand", start_s=14, end_s=15),
        RunWalkSpan(span_type="run", start_s=17, end_s=18),
    ]

    mask = active_running_display_mask(elapsed, spans)

    assert mask[10:] == [True, False, False, True, False, False, True, True, True, True]


def test_display_mask_preserves_values_and_source_nulls_positionally():
    values = [1.0, None, 3.0]

    result = apply_display_mask(values, [True, True, False])

    assert result == [1.0, None, None]


def test_display_mask_preserves_absent_channel_as_empty():
    assert apply_display_mask([], [True, False]) == []


def test_display_mask_returns_aligned_nulls_for_malformed_nonempty_channel():
    assert apply_display_mask([1.0], [True, False]) == [None, None]


def test_distance_median_flattens_subthreshold_waterfront_noise():
    profile = smooth_elevation_by_distance(
        distance_m=[0.0, 50.0, 100.0, 150.0, 200.0, 250.0],
        altitude_m=[0.0, 1.0, -1.0, 1.0, -1.0, 0.0],
    )

    assert profile is not None
    assert elevation_gain_loss_m(profile) == (0.0, 0.0)


def test_distance_median_preserves_climb_wider_than_window():
    profile = smooth_elevation_by_distance(
        distance_m=[0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0],
        altitude_m=[0.0, 0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 10.0],
    )

    assert profile is not None
    gain, loss = elevation_gain_loss_m(profile)
    assert gain >= 9.0
    assert loss == 0.0


def test_distance_median_preserves_null_gap_without_cross_segment_smoothing():
    profile = smooth_elevation_by_distance(
        distance_m=[0.0, 50.0, None, 200.0, 250.0],
        altitude_m=[0.0, 2.0, None, 10.0, 12.0],
    )

    assert profile == [1.0, 1.0, None, 11.0, 11.0]


def test_distance_median_breaks_at_nonmonotonic_distance():
    profile = smooth_elevation_by_distance(
        distance_m=[0.0, 50.0, 40.0, 90.0],
        altitude_m=[0.0, 2.0, 10.0, 12.0],
    )

    assert profile == [1.0, 1.0, 11.0, 11.0]


def test_distance_median_rejects_empty_or_misaligned_inputs():
    assert smooth_elevation_by_distance([], []) is None
    assert smooth_elevation_by_distance([0.0], [0.0, 1.0]) is None


def test_elevation_hysteresis_ignores_change_below_three_meters():
    assert elevation_gain_loss_m([0.0, 2.99]) == (0.0, 0.0)


def test_elevation_hysteresis_counts_exact_three_meter_climb():
    assert elevation_gain_loss_m([0.0, 3.0]) == (3.0, 0.0)


def test_elevation_hysteresis_counts_descent_above_three_meters():
    assert elevation_gain_loss_m([3.01, 0.0]) == (0.0, 3.01)


def test_elevation_hysteresis_does_not_accumulate_repeated_small_reversals():
    assert elevation_gain_loss_m([0.0, 2.9, 0.0, 2.9, 0.0]) == (0.0, 0.0)


def test_elevation_hysteresis_does_not_bridge_null_separated_segments():
    assert elevation_gain_loss_m([0.0, 5.0, None, 10.0, 5.0]) == (5.0, 5.0)


def test_closed_loop_elevation_removes_linear_endpoint_drift():
    corrected = detrend_closed_loop_elevation(
        distance_m=[0.0, 50.0, 100.0],
        altitude_m=[0.0, 4.0, -2.0],
        start_lat=40.7206,
        start_lon=-74.0415,
        end_lat=40.7206,
        end_lon=-74.0415,
    )

    assert corrected == [0.0, 5.0, 0.0]


def test_point_to_point_elevation_preserves_real_endpoint_difference():
    corrected = detrend_closed_loop_elevation(
        distance_m=[0.0, 50.0, 100.0],
        altitude_m=[0.0, 4.0, 10.0],
        start_lat=40.7206,
        start_lon=-74.0415,
        end_lat=40.7306,
        end_lon=-74.0415,
    )

    assert corrected == [0.0, 4.0, 10.0]


def test_elevation_drift_correction_requires_complete_endpoint_coordinates():
    corrected = detrend_closed_loop_elevation(
        distance_m=[0.0, 100.0],
        altitude_m=[0.0, -2.0],
        start_lat=None,
        start_lon=-74.0415,
        end_lat=40.7206,
        end_lon=-74.0415,
    )

    assert corrected == [0.0, -2.0]


def test_zone_display_omits_fit_below_bucket_and_uses_exclusive_boundaries():
    rows = zone_display_rows(
        times_s=[16.686, 22.001, 780.962, 2216.783, 0.0, 0.0, 7.5],
        boundaries=[94, 110, 130, 148, 161, 181],
        unit="bpm",
    )

    assert [
        (row.zone, row.label, row.lower_bound, row.upper_bound, row.duration_s)
        for row in rows
    ] == [
        (1, "Z1 · 94–109 bpm", 94, 109, 22.001),
        (2, "Z2 · 110–129 bpm", 110, 129, 780.962),
        (3, "Z3 · 130–147 bpm", 130, 147, 2216.783),
        (4, "Z4 · 148–160 bpm", 148, 160, 0.0),
        (5, "Z5 · ≥161 bpm", 161, None, 7.5),
    ]


def test_zone_display_preserves_missing_durations_instead_of_zero_filling():
    rows = zone_display_rows(
        times_s=[1.0, None, 2.0, 3.0, 4.0, None, None],
        boundaries=[94, 110, 130, 148, 161, 181],
        unit="bpm",
    )

    assert rows[0].duration_s is None
    assert rows[-1].duration_s is None


def test_zone_display_requires_complete_contiguous_boundaries():
    assert zone_display_rows([1.0, 2.0], [94], unit="bpm") == []
    assert zone_display_rows([1.0, 2.0, 3.0], [94, None, 130], unit="bpm") == []


def test_zone_display_caps_numbered_zones_at_five_and_folds_all_overflow():
    rows = zone_display_rows(
        times_s=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        boundaries=[94, 110, 130, 148, 161, 181, 200],
        unit="bpm",
    )

    assert [row.zone for row in rows] == [1, 2, 3, 4, 5]
    assert rows[-1].label == "Z5 · ≥161 bpm"
    assert rows[-1].duration_s == 21.0


def test_zone_display_rejects_duplicate_or_decreasing_boundaries():
    assert zone_display_rows([1.0, 2.0, 3.0], [94, 94, 130], unit="bpm") == []
    assert zone_display_rows([1.0, 2.0, 3.0], [110, 100, 130], unit="bpm") == []
