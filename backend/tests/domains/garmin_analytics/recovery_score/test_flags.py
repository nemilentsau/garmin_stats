"""Personal robust health-flag thresholds, the 'unknown' state, and structural gaps (R9)."""

from app.domains.garmin_analytics.domain.recovery_score.flags import (
    oxygen_flag_state,
    structural_gaps,
    thermo_flag_state,
)


def test_oxygen_missing_value_is_unknown_not_clear():
    state, _threshold = oxygen_flag_state(None, history=[93.0] * 40)
    assert state == "unknown"


def test_oxygen_flags_a_value_below_the_personal_threshold():
    history = [93.0, 92.0, 94.0] * 14  # spread present so the threshold is meaningful
    state, threshold = oxygen_flag_state(82.0, history=history)
    assert state == "flag" and threshold is not None and threshold > 82.0


def test_oxygen_clear_at_a_typical_value():
    state, _threshold = oxygen_flag_state(93.0, history=[93.0, 92.0, 94.0] * 14)
    assert state == "clear"


def test_oxygen_clear_with_insufficient_history():
    state, threshold = oxygen_flag_state(80.0, history=[93.0] * 10)
    assert state == "clear" and threshold is None


def test_thermo_flags_both_directions():
    history = [0.1, -0.1, 0.2, -0.2] * 10
    assert thermo_flag_state(1.5, history=history)[0] == "flag"
    assert thermo_flag_state(-1.5, history=history)[0] == "flag"


def test_thermo_clear_near_baseline():
    history = [0.1, -0.1, 0.2, -0.2] * 10
    assert thermo_flag_state(0.05, history=history)[0] == "clear"


def test_thermo_missing_value_is_unknown():
    assert thermo_flag_state(None, history=[0.0] * 40)[0] == "unknown"


def test_structural_gaps_finds_blocks_not_singletons():
    dates = [f"2025-06-{day:02d}" for day in range(1, 11)]
    present = [True, False, False, False, True, True, False, True, True, True]
    # the 3-day run qualifies; the lone False on day 7 does not
    assert structural_gaps(dates, present, min_len=3) == [("2025-06-02", "2025-06-04")]


def test_structural_gap_at_series_end_is_captured():
    dates = ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"]
    present = [True, False, False, False]
    assert structural_gaps(dates, present, min_len=3) == [("2025-06-02", "2025-06-04")]
