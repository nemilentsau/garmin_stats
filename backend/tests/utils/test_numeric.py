"""Tests for shared nullable numeric helpers."""

from app.utils.numeric import safe_avg, safe_median, safe_percentile


class TestSafeHelpers:
    def test_avg_returns_rounded_mean_for_nonempty_list(self):
        assert safe_avg([10, 20, 30]) == 20.0

    def test_avg_returns_none_for_empty_list(self):
        assert safe_avg([]) is None

    def test_median_returns_middle_value(self):
        assert safe_median([1, 3, 2]) == 2.0

    def test_median_returns_none_for_empty_list(self):
        assert safe_median([]) is None

    def test_percentile_returns_interpolated_value(self):
        values = list(range(1, 101))
        assert safe_percentile(values, 25) == 25.8

    def test_percentile_returns_none_for_empty_list(self):
        assert safe_percentile([], 50) is None
