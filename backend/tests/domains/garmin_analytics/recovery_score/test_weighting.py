"""Recovery-signed correlation-deflated weighting, renormalization, and the >=5/7 gate."""

import math

from app.domains.garmin_analytics.domain.recovery_score.weighting import (
    DEFLATED_WEIGHTS,
    RECOVERY_SIGNS,
    weighted_recovery_score,
)

_AXIS_KEYS = {
    "heart_rate_resting",
    "heart_rate_avg",
    "stress_avg",
    "respiration_avg",
    "body_battery_avg",
    "hrv_nightly_avg",
    "sleep_score",
}


def test_signs_and_weights_cover_exactly_the_seven_axis_metrics():
    assert set(RECOVERY_SIGNS) == _AXIS_KEYS == set(DEFLATED_WEIGHTS)


def test_weights_sum_to_one():
    assert math.isclose(sum(DEFLATED_WEIGHTS.values()), 1.0, abs_tol=1e-6)


def test_recovery_positive_inputs_yield_positive_score():
    # +1 z in the recovery-improving direction for every metric
    raw_z = {
        "hrv_nightly_avg": 1.0,
        "body_battery_avg": 1.0,
        "sleep_score": 1.0,
        "heart_rate_resting": -1.0,
        "heart_rate_avg": -1.0,
        "stress_avg": -1.0,
        "respiration_avg": -1.0,
    }
    score, n = weighted_recovery_score(raw_z)
    assert score is not None and score > 0 and n == 7


def test_present_weights_renormalize_when_two_inputs_missing():
    # Five present (resting HR + HR-avg missing), each a +2.0 recovery-positive
    # contribution. Renormalizing over the present weights (not the full seven) must
    # recover +2.0 exactly; dividing by all seven weights would understate it.
    raw_z = {
        "hrv_nightly_avg": 2.0,
        "body_battery_avg": 2.0,
        "sleep_score": 2.0,
        "stress_avg": -2.0,
        "respiration_avg": -2.0,
    }
    score, n = weighted_recovery_score(raw_z)
    assert score is not None and math.isclose(score, 2.0, abs_tol=1e-9) and n == 5


def test_exactly_five_present_is_scored():
    raw_z = {
        "hrv_nightly_avg": 1.0,
        "body_battery_avg": 1.0,
        "sleep_score": 1.0,
        "stress_avg": -1.0,
        "respiration_avg": -1.0,
    }
    score, n = weighted_recovery_score(raw_z)
    assert score is not None and n == 5


def test_four_present_returns_none_but_reports_count():
    raw_z = {
        "hrv_nightly_avg": 1.0,
        "sleep_score": 1.0,
        "body_battery_avg": 1.0,
        "stress_avg": -1.0,
    }
    score, n = weighted_recovery_score(raw_z)
    assert score is None and n == 4


def test_none_valued_inputs_are_not_counted_present():
    raw_z = {k: None for k in _AXIS_KEYS}
    score, n = weighted_recovery_score(raw_z)
    assert score is None and n == 0
