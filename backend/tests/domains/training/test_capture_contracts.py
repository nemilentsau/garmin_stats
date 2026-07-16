"""Training capture wire constraints at the mutation boundary."""

import pytest
from pydantic import ValidationError

from app.domains.training.contracts import TrainingCaptureLog


def _capture(**set_overrides):
    set_log = {"set_index": 0, "weight": 0, "reps": 0, "rir": 0}
    set_log.update(set_overrides)
    return {
        "set_logs": [{"exercise_id": "squat", "sets": [set_log]}],
        "checkin": {"soreness": {"quad": 0}, "flags": {}, "core_done": False},
        "rpe": 1,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("set_index", -1),
        ("weight", -0.01),
        ("reps", -1),
        ("rir", -1),
        ("rir", 11),
    ],
)
def test_set_capture_rejects_values_outside_ui_supported_ranges(field, value):
    with pytest.raises(ValidationError):
        TrainingCaptureLog.model_validate(_capture(**{field: value}))


@pytest.mark.parametrize("soreness", [-1, 4])
def test_checkin_soreness_rejects_values_outside_zero_to_three(soreness: int):
    payload = _capture()
    payload["checkin"]["soreness"]["quad"] = soreness

    with pytest.raises(ValidationError):
        TrainingCaptureLog.model_validate(payload)


@pytest.mark.parametrize("rpe", [0, 11])
def test_capture_rpe_rejects_values_outside_one_to_ten(rpe: int):
    payload = _capture()
    payload["rpe"] = rpe

    with pytest.raises(ValidationError):
        TrainingCaptureLog.model_validate(payload)


def test_capture_accepts_each_numeric_boundary():
    low = TrainingCaptureLog.model_validate(_capture())
    high_payload = _capture(set_index=0, weight=0, reps=0, rir=10)
    high_payload["checkin"]["soreness"]["quad"] = 3
    high_payload["rpe"] = 10
    high = TrainingCaptureLog.model_validate(high_payload)

    assert low.set_logs[0].sets[0].rir == 0
    assert high.set_logs[0].sets[0].rir == 10
    assert high.checkin is not None
    assert high.checkin.soreness == {"quad": 3}


@pytest.mark.parametrize(
    "payload",
    [
        {**_capture(), "unknown": True},
        {
            **_capture(),
            "set_logs": [
                {"exercise_id": "squat", "sets": [{"set_index": 0, "unknown": True}]}
            ],
        },
        {
            **_capture(),
            "checkin": {"soreness": {}, "flags": {}, "core_done": False, "unknown": True},
        },
    ],
)
def test_capture_rejects_unknown_nested_fields(payload):
    with pytest.raises(ValidationError):
        TrainingCaptureLog.model_validate(payload)
