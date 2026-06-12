"""Expanding robust-z normalization: warm-up boundary, current-day exclusion, fallback.

Covers the warm-up boundary (29 vs 30 prior present days), exclusion of the current day
from its own baseline, None-skipping, the degenerate-spread std fallback, and the
baseline-median sibling used by the evidence rows.
"""

import math

from app.domains.garmin_analytics.domain.recovery_score.normalization import (
    expanding_baseline_median,
    expanding_robust_z,
)


def test_warmup_returns_none_with_only_29_prior_present_days():
    values = [1.0] * 29 + [5.0]  # index 29 has 29 priors -> below the 30 floor
    assert expanding_robust_z(values)[29] is None


def test_value_defined_at_exactly_30_prior_present_days():
    values = list(range(30)) + [100.0]  # index 30 has exactly 30 priors
    assert expanding_robust_z(values)[30] is not None


def test_current_day_excluded_from_its_own_baseline():
    values = [10.0] * 30 + [10.0]  # baseline all 10s, current 10 -> z 0
    assert expanding_robust_z(values)[30] == 0.0


def test_none_inputs_are_skipped_not_counted_as_present():
    values = [1.0] * 20 + [None] * 5 + [1.0] * 10 + [9.0]
    out = expanding_robust_z(values)
    assert out[35] is not None  # 30 present priors despite the 5 None days
    assert out[22] is None  # a missing day is itself None


def test_degenerate_spread_falls_back_to_std_and_stays_finite():
    values = [5.0] * 30 + [6.0]  # MAD == 0 -> std fallback
    out = expanding_robust_z(values)
    assert out[30] is not None and math.isfinite(out[30])


def test_baseline_median_aligns_with_z_warmup_and_value():
    values = [4.0] * 30 + [9.0]
    medians = expanding_baseline_median(values)
    assert medians[29] is None  # same 30-day warm-up as the z
    assert medians[30] == 4.0  # median of the prior 30 fours
