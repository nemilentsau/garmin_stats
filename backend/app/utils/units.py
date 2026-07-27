"""Imperial conversion helpers shared across read layers (imperial display rule).

CLAUDE.md: display units are US imperial (miles, min/mi, ft, °F); storage and
canonical contracts stay FIT-native metric. `M_PER_MI`/`KM_TO_MI` are exact
(not approximated) so repeated conversions stay consistent across call sites.
"""

M_PER_MI = 1609.344
KM_TO_MI = 1.609344


def m_to_mi(value_m: float | None) -> float | None:
    """Meters -> miles, 2dp. None-preserving."""
    return None if value_m is None else round(value_m / M_PER_MI, 2)


def m_to_mi_exact(value_m: float | None) -> float | None:
    """Meters -> miles without display rounding. None-preserving."""
    return None if value_m is None else value_m / M_PER_MI


def min_per_km_to_min_per_mi(value_min_per_km: float | None) -> float | None:
    """min/km -> min/mi, 2dp. None-preserving."""
    return None if value_min_per_km is None else round(value_min_per_km * KM_TO_MI, 2)


def c_to_f(value_c: float | None) -> float | None:
    """Absolute Celsius temperature -> Fahrenheit, 1dp. None-preserving."""
    return None if value_c is None else round(value_c * 9 / 5 + 32, 1)


def c_delta_to_f_delta(value_c: float | None) -> float | None:
    """Celsius temperature deviation -> Fahrenheit deviation, 2dp."""
    return None if value_c is None else round(value_c * 9 / 5, 2)
