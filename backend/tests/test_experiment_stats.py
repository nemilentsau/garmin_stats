"""Unit tests for experiment statistical functions."""


import warnings

import pytest

from app.models import (
    DailyBodyBatteryStats,
    DailyCheckIn,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
)
from app.services.experiment_stats import (
    autocorrelation_lag1,
    compute_cohens_d,
    compute_hedges_g,
    compute_nap,
    linear_trend,
    permutation_test,
    resolve_checkin_path,
    resolve_metric_path,
    resolve_path,
    welch_t_test,
)


def _make_metric(
    date: str = "2026-01-01",
    hrv_nightly: float | None = 45.0,
    sleep_score: int | None = 80,
    resting_hr: int | None = 55,
) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(resting=resting_hr),
        stress=DailyMetricStats(),
        body_battery=DailyBodyBatteryStats(),
        spo2=DailyMetricStats(),
        respiration=DailyMetricStats(),
        hrv=DailyHrvStats(nightly_avg=hrv_nightly, weekly_avg=42.0),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(),
    )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestResolveMetricPath:
    def test_simple_nested(self):
        m = _make_metric(hrv_nightly=48.5)
        assert resolve_metric_path(m, "hrv.nightly_avg") == 48.5

    def test_deep_nested(self):
        m = _make_metric(sleep_score=85)
        assert resolve_metric_path(m, "sleep.score") == 85.0

    def test_integer_field(self):
        m = _make_metric(resting_hr=52)
        assert resolve_metric_path(m, "heart_rate.resting") == 52.0

    def test_none_value(self):
        m = _make_metric(hrv_nightly=None)
        assert resolve_metric_path(m, "hrv.nightly_avg") is None

    def test_invalid_path(self):
        m = _make_metric()
        assert resolve_metric_path(m, "nonexistent.field") is None

    def test_partial_path(self):
        m = _make_metric()
        # "hrv" alone returns a DailyHrvStats, not a number
        assert resolve_metric_path(m, "hrv") is None


class TestResolveCheckinPath:
    def test_bool_flag(self):
        c = DailyCheckIn(id="c1", date="2026-01-01", alcohol_flag=True)
        assert resolve_checkin_path(c, "alcohol_flag") is True

    def test_numeric_field(self):
        c = DailyCheckIn(id="c1", date="2026-01-01", energy=7)
        assert resolve_checkin_path(c, "energy") == 7.0

    def test_none_field(self):
        c = DailyCheckIn(id="c1", date="2026-01-01")
        assert resolve_checkin_path(c, "energy") is None


class TestResolvePath:
    def test_metric_dispatch(self):
        m = _make_metric(hrv_nightly=50.0)
        assert resolve_path(m, None, "hrv.nightly_avg") == 50.0

    def test_checkin_dispatch(self):
        c = DailyCheckIn(id="c1", date="2026-01-01", travel_flag=True)
        assert resolve_path(None, c, "checkin.travel_flag") is True

    def test_missing_metric(self):
        assert resolve_path(None, None, "hrv.nightly_avg") is None


# ---------------------------------------------------------------------------
# NAP
# ---------------------------------------------------------------------------


class TestNAP:
    def test_complete_separation(self):
        baseline = [1.0, 2.0, 3.0]
        treatment = [4.0, 5.0, 6.0]
        nap, interp = compute_nap(baseline, treatment)
        assert nap == 1.0
        assert interp == "large"

    def test_no_effect(self):
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0]
        treatment = [1.0, 2.0, 3.0, 4.0, 5.0]
        nap, interp = compute_nap(baseline, treatment)
        assert nap == 0.5
        assert interp == "no_effect"

    def test_partial_overlap(self):
        baseline = [1.0, 2.0, 3.0, 4.0]
        treatment = [3.0, 4.0, 5.0, 6.0]
        nap, interp = compute_nap(baseline, treatment)
        assert 0.5 < nap < 1.0

    def test_empty_input(self):
        nap, interp = compute_nap([], [1.0, 2.0])
        assert nap == 0.5
        assert interp == "no_effect"


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------


class TestEffectSizes:
    def test_cohens_d_large(self):
        baseline = [10.0] * 20
        treatment = [20.0] * 20
        d = compute_cohens_d(baseline, treatment)
        # Perfect separation → very large d (approaches inf with zero variance,
        # but since all values are identical, sd=0 → returns 0)
        assert d == 0.0  # degenerate: zero variance

    def test_cohens_d_with_variance(self):
        baseline = [10.0, 12.0, 11.0, 9.0, 13.0]
        treatment = [15.0, 17.0, 16.0, 14.0, 18.0]
        d = compute_cohens_d(baseline, treatment)
        assert d > 2.0  # Large effect

    def test_hedges_correction(self):
        baseline = [10.0, 12.0, 11.0, 9.0, 13.0]
        treatment = [15.0, 17.0, 16.0, 14.0, 18.0]
        d, g = compute_hedges_g(baseline, treatment)
        assert abs(g) < abs(d)  # Hedges' g always smaller in magnitude

    def test_small_sample(self):
        d, g = compute_hedges_g([1.0], [2.0])
        assert d == 0.0  # Too few for pooled SD


# ---------------------------------------------------------------------------
# Significance tests
# ---------------------------------------------------------------------------


class TestPermutationTest:
    def test_large_effect(self):
        baseline = [10.0, 11.0, 12.0, 9.0, 10.0, 11.0, 10.0]
        treatment = [20.0, 21.0, 22.0, 19.0, 20.0, 21.0, 20.0]
        p = permutation_test(baseline, treatment, n_perms=5000, seed=42)
        assert p < 0.01

    def test_no_effect(self):
        baseline = [10.0, 11.0, 12.0, 9.0, 10.0]
        treatment = [10.0, 11.0, 12.0, 9.0, 10.0]
        p = permutation_test(baseline, treatment, n_perms=5000, seed=42)
        assert p > 0.3

    def test_empty(self):
        assert permutation_test([], [1.0]) == 1.0


class TestWelchT:
    def test_significant(self):
        baseline = [10.0, 11.0, 12.0, 9.0, 10.0, 11.0, 10.0]
        treatment = [20.0, 21.0, 22.0, 19.0, 20.0, 21.0, 20.0]
        p = welch_t_test(baseline, treatment)
        assert p < 0.001

    def test_not_significant(self):
        baseline = [10.0, 11.0, 12.0]
        treatment = [10.5, 11.5, 12.5]
        p = welch_t_test(baseline, treatment)
        assert p > 0.05

    def test_constant_identical_series_returns_non_significant(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            p = welch_t_test([10.0, 10.0, 10.0], [10.0, 10.0, 10.0])
        assert p == 1.0

    def test_constant_separated_series_returns_significant_without_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            p = welch_t_test([10.0, 10.0, 10.0], [20.0, 20.0, 20.0])
        assert p == 0.0

    def test_insufficient_data(self):
        assert welch_t_test([1.0], [2.0]) == 1.0


# ---------------------------------------------------------------------------
# Trend & autocorrelation
# ---------------------------------------------------------------------------


class TestLinearTrend:
    def test_upward_trend(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        slope, p = linear_trend(values)
        assert slope == pytest.approx(1.0, abs=0.01)
        assert p < 0.001

    def test_flat(self):
        values = [5.0, 5.0, 5.0, 5.0, 5.0]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            slope, p = linear_trend(values)
        assert slope == pytest.approx(0.0, abs=0.01)
        assert p == 1.0

    def test_too_few(self):
        slope, p = linear_trend([1.0, 2.0])
        assert slope == 0.0
        assert p == 1.0


class TestAutocorrelation:
    def test_high_autocorrelation(self):
        # Smooth upward series has high autocorrelation
        values = [float(i) for i in range(20)]
        ac = autocorrelation_lag1(values)
        assert ac > 0.9

    def test_low_autocorrelation(self):
        # Alternating values
        values = [1.0, 10.0, 1.0, 10.0, 1.0, 10.0, 1.0, 10.0]
        ac = autocorrelation_lag1(values)
        assert ac < -0.5

    def test_constant_series_returns_zero(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            value = autocorrelation_lag1([4.0, 4.0, 4.0, 4.0, 4.0])
        assert value == 0.0

    def test_too_few(self):
        assert autocorrelation_lag1([1.0, 2.0]) == 0.0
