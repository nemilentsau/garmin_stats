"""Unit tests for the trailing robust baseline primitive."""

from typing import cast

from app.domains.garmin_analytics.domain.primitives import trends


def test_insufficient_prior_nights_yields_empty_point():
    # 20 priors before index 20, min_days is 21 -> empty point.
    values: list[float | None] = cast(list[float | None], [60.0] * 21)
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    assert band[20] == trends.TrailingBandPoint(None, None, None, None, False)


def test_band_brackets_median_and_excludes_current_night():
    # Priors 40..61 (22 present values) -> median 50.5; current 50.0 is central.
    values: list[float | None] = cast(
        list[float | None], [40.0 + i for i in range(22)] + [50.0]
    )
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    point = band[22]
    assert point.median == 50.5  # would shift if current (50.0) were included
    assert point.band_low is not None and point.band_high is not None
    assert point.band_low < 50.5 < point.band_high
    assert point.z is not None
    assert point.is_extreme is False


def test_far_outlier_is_flagged_extreme():
    values: list[float | None] = cast(
        list[float | None], [40.0 + i for i in range(22)] + [200.0]
    )
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    assert band[22].is_extreme is True
    assert band[22].z is not None and band[22].z > 2.0


def test_missing_current_value_keeps_band_but_no_z():
    values: list[float | None] = [40.0 + i for i in range(22)] + [None]  # type: ignore[assignment]
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    point = band[22]
    assert point.band_low is not None
    assert point.z is None
    assert point.is_extreme is False


def test_window_limits_lookback():
    # window=21 means index 22 looks at indices 1..21 (21 values), index 0 dropped.
    values: list[float | None] = cast(
        list[float | None], [40.0 + i for i in range(22)] + [50.0]
    )
    band = trends.trailing_robust_band(values, window=21, min_days=21)
    assert band[22].median == 51.0  # median of 41..61
