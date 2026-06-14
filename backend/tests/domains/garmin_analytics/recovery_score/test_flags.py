"""Personal robust health-flag thresholds, unknown readings, and structural gaps (R9)."""

from app.domains.garmin_analytics.domain.recovery_score.flags import (
    oxygen_flag_status,
    structural_gaps,
    thermo_flag_status,
)


def test_oxygen_missing_value_is_unknown_not_normal():
    status, _threshold = oxygen_flag_status(None, history=[93.0] * 40)
    assert status == "unknown"


def test_oxygen_flags_a_value_below_the_personal_threshold():
    history = [93.0, 92.0, 94.0] * 14  # spread present so the threshold is meaningful
    status, threshold = oxygen_flag_status(82.0, history=history)
    assert status == "low" and threshold is not None and threshold > 82.0


def test_oxygen_normal_at_a_typical_value():
    status, _threshold = oxygen_flag_status(93.0, history=[93.0, 92.0, 94.0] * 14)
    assert status == "normal"


def test_oxygen_normal_with_insufficient_history():
    status, threshold = oxygen_flag_status(80.0, history=[93.0] * 10)
    assert status == "normal" and threshold is None


def test_thermo_distinguishes_below_and_above_usual():
    history = [0.1, -0.1, 0.2, -0.2] * 10
    assert thermo_flag_status(1.5, history=history)[0] == "above_usual"
    assert thermo_flag_status(-1.5, history=history)[0] == "below_usual"


def test_thermo_normal_near_baseline():
    history = [0.1, -0.1, 0.2, -0.2] * 10
    assert thermo_flag_status(0.05, history=history)[0] == "normal"


def test_thermo_missing_value_is_unknown():
    assert thermo_flag_status(None, history=[0.0] * 40)[0] == "unknown"


def test_structural_gaps_finds_blocks_not_singletons():
    dates = [f"2025-06-{day:02d}" for day in range(1, 11)]
    present = [True, False, False, False, True, True, False, True, True, True]
    # the 3-day run qualifies; the lone False on day 7 does not
    assert structural_gaps(dates, present, min_len=3) == [("2025-06-02", "2025-06-04")]


def test_structural_gap_at_series_end_is_captured():
    dates = ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"]
    present = [True, False, False, False]
    assert structural_gaps(dates, present, min_len=3) == [("2025-06-02", "2025-06-04")]
