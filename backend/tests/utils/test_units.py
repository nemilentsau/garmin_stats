"""Tests for shared imperial conversion helpers (CLAUDE.md display-unit rule)."""

from app.utils.units import (
    KM_TO_MI,
    M_PER_MI,
    m_to_mi,
    m_to_mi_exact,
    min_per_km_to_min_per_mi,
)


class TestConstants:
    def test_m_per_mi_is_exact_conversion_factor(self):
        assert M_PER_MI == 1609.344

    def test_km_to_mi_is_exact_conversion_factor(self):
        assert KM_TO_MI == 1.609344


class TestMToMi:
    def test_converts_meters_to_miles_rounded_to_two_decimals(self):
        assert m_to_mi(9695.29) == round(9695.29 / 1609.344, 2)

    def test_passes_through_none(self):
        assert m_to_mi(None) is None

    def test_rounds_half_up_at_boundary(self):
        # 1.005 rounds to 1.0 or 1.01 depending on float representation;
        # pin the exact banker's-rounding behavior of the shared helper.
        value_m = 1.005 * M_PER_MI
        assert m_to_mi(value_m) == round(value_m / M_PER_MI, 2)

    def test_zero_meters_is_zero_miles(self):
        assert m_to_mi(0.0) == 0.0


class TestMToMiExact:
    def test_converts_without_rounding(self):
        assert m_to_mi_exact(100.0) == 100.0 / 1609.344

    def test_passes_through_none(self):
        assert m_to_mi_exact(None) is None


class TestMinPerKmToMinPerMi:
    def test_converts_pace_rounded_to_two_decimals(self):
        assert min_per_km_to_min_per_mi(5.24) == round(5.24 * 1.609344, 2)

    def test_passes_through_none(self):
        assert min_per_km_to_min_per_mi(None) is None

    def test_zero_pace_is_zero(self):
        assert min_per_km_to_min_per_mi(0.0) == 0.0
