"""Data-driven regime detection: run length, band edges, gap merging, None handling."""

from app.domains.garmin_analytics.domain.recovery_score.regimes import (
    MIN_RUN_DAYS,
    detect_regimes,
)


def _dates(n: int) -> list[str]:
    return [f"2025-06-{d:02d}" if d < 32 else f"2025-07-{d - 31:02d}" for d in range(1, n + 1)]


def test_sustained_low_run_is_detected():
    ma7 = [-1.0] * MIN_RUN_DAYS
    regimes = detect_regimes(_dates(MIN_RUN_DAYS), ma7)
    assert len(regimes) == 1 and regimes[0].kind == "low"
    assert regimes[0].start == "2025-06-01"


def test_run_one_day_short_is_ignored():
    ma7 = [-1.0] * (MIN_RUN_DAYS - 1)
    assert detect_regimes(_dates(MIN_RUN_DAYS - 1), ma7) == []


def test_band_edge_is_inclusive_low_and_elevated():
    n = MIN_RUN_DAYS
    assert detect_regimes(_dates(n), [-0.5] * n)[0].kind == "low"  # <= -0.5
    assert detect_regimes(_dates(n), [0.5] * n)[0].kind == "elevated"  # >= +0.5


def test_inside_band_is_not_a_regime():
    n = MIN_RUN_DAYS
    assert detect_regimes(_dates(n), [-0.49] * n) == []
    assert detect_regimes(_dates(n), [0.0] * n) == []


def test_short_in_band_gap_merges_two_low_runs():
    # 8 low, 2 in-band (<= 3 merge gap), 8 low -> one merged 18-day regime
    ma7 = [-1.0] * 8 + [0.0] * 2 + [-1.0] * 8
    regimes = detect_regimes(_dates(18), ma7)
    assert len(regimes) == 1 and regimes[0].start == "2025-06-01" and regimes[0].end == "2025-06-18"


def test_large_gap_does_not_merge():
    # 8 low, 5 in-band (> 3 gap), 8 low -> neither sub-run reaches 14, so none
    ma7 = [-1.0] * 8 + [0.0] * 5 + [-1.0] * 8
    assert detect_regimes(_dates(21), ma7) == []


def test_none_warmup_does_not_start_a_regime():
    ma7 = [None] * 5 + [-1.0] * MIN_RUN_DAYS
    regimes = detect_regimes(_dates(5 + MIN_RUN_DAYS), ma7)
    assert len(regimes) == 1 and regimes[0].start == "2025-06-06"
