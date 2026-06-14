"""Seeded trailing-7 MA: the seed fills the left edge so the display window doesn't ramp."""

from app.domains.garmin_analytics.domain.recovery_score.smoothing import (
    BAND_MIN_VALID,
    BAND_WINDOW,
    seeded_ma7,
    seeded_sd,
)


def test_seeded_left_edge_pulls_toward_the_seed():
    seeded = seeded_ma7([0.0] * 6, [3.0, 3.0, 3.0])
    assert seeded[0] is not None and seeded[0] < 3.0  # blends the six prior zeros
    assert len(seeded) == 3  # only the display portion is returned


def test_no_seed_equals_plain_trailing_ma_at_left_edge():
    assert seeded_ma7([], [1.0, 2.0, 3.0])[0] == 1.0


def test_full_seed_window_recovers_the_true_trailing_mean():
    seeded = seeded_ma7([3.0] * 6, [3.0])
    assert seeded[0] == 3.0  # seven 3.0s -> 3.0, no left-edge artifact


def test_none_values_in_window_are_skipped():
    assert seeded_ma7([], [2.0, None, 4.0])[2] == 3.0  # mean(2, 4)


def test_all_none_window_yields_none():
    assert seeded_ma7([], [None, None])[0] is None


def test_seeded_sd_returns_only_display_portion():
    seed = [0.0] * BAND_WINDOW  # plenty of prior days
    display = [1.0, 2.0, 3.0]
    assert len(seeded_sd(seed, display)) == 3


def test_seeded_sd_uses_seed_to_fill_left_edge():
    # First display point sees its 13 seed days + itself -> a real SD, not None.
    seed = [1.0] * (BAND_WINDOW - 1)
    display = [2.0]
    out = seeded_sd(seed, display)
    assert out[0] is not None


def test_seeded_sd_none_when_too_few_inputs():
    # No seed, single display value -> below BAND_MIN_VALID -> None.
    assert seeded_sd([], [5.0])[0] is None
    assert BAND_MIN_VALID == 5
    assert BAND_WINDOW == 14
