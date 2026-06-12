"""Meaningful-change thresholds, score band, and trend direction (R2 + Q4.1).

Each comparison earns a test at the boundary and on each side.
"""

from app.domains.garmin_analytics.domain.recovery_score.thresholds import (
    T1,
    T7,
    is_acute_delta1,
    is_meaningful_delta7,
    score_band,
    trend_direction,
)


def test_thresholds_are_the_validated_values():
    assert T7 == 0.97 and T1 == 1.86


def test_delta7_at_and_around_the_boundary():
    assert is_meaningful_delta7(0.97)
    assert is_meaningful_delta7(-0.97)
    assert not is_meaningful_delta7(0.96)


def test_delta1_at_and_around_the_boundary():
    assert is_acute_delta1(-1.86)
    assert is_acute_delta1(1.86)
    assert not is_acute_delta1(-1.85)


def test_score_band_cuts_at_plus_minus_half():
    assert score_band(-0.5) == "suppressed"  # boundary, inclusive low
    assert score_band(-0.49) == "typical"
    assert score_band(0.0) == "typical"
    assert score_band(0.49) == "typical"
    assert score_band(0.5) == "strong"  # boundary, inclusive high


def test_trend_direction_uses_the_delta7_threshold():
    assert trend_direction(0.97) == "improving"
    assert trend_direction(0.96) == "steady"
    assert trend_direction(-0.97) == "declining"
    assert trend_direction(-0.96) == "steady"
