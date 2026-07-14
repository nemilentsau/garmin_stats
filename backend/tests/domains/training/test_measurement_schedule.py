"""Pure read-time policy for authored measurement attempts and backup days."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from app.domains.training.application.compile import compile_schedule
from app.domains.training.application.measurement_schedule import resolve_measurement_day
from app.domains.training.contracts import (
    MeasurementEvent,
    MeasurementStatus,
    V3Block,
    V3Bundle,
)
from tests._architecture import REPO_ROOT

BLOCK1 = REPO_ROOT / "docs" / "routine-pivot" / "block1"


def _load(name: str) -> dict:
    return json.loads((BLOCK1 / name).read_text(encoding="utf-8"))


def _block_and_schedule():
    block = V3Block.model_validate(_load("block1.json"))
    bundles = [
        V3Bundle.model_validate(_load(name))
        for name in ("running_v3.json", "strength_v3.json", "support_v3.json")
    ]
    return block, compile_schedule(bundles)


def _running_card_ids(entries) -> list[str]:
    return [entry.card.id for entry in entries if entry.bundle_id == "running.v3"]


def test_valid_scheduled_attempt_keeps_authored_backup_day_run():
    block, schedule = _block_and_schedule()

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={"ev_lthr_test": {1: "valid"}},
    )

    assert _running_card_ids(result.entries) == ["run.tempo"]
    assert result.backup_event_ids == frozenset()


@pytest.mark.parametrize("status", ["awaiting_review", "provisional", "failed"])
def test_non_valid_scheduled_attempt_activates_authored_backup(status: MeasurementStatus):
    block, schedule = _block_and_schedule()

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={"ev_lthr_test": {1: status}},
    )

    assert _running_card_ids(result.entries) == ["run.lthr_test"]
    assert result.backup_event_ids == frozenset({"ev_lthr_test"})
    assert {entry.bundle_id for entry in result.entries} == {
        "running.v3",
        "strength.v3",
        "support.v3",
    }


def test_missing_scheduled_attempt_activates_authored_backup():
    block, schedule = _block_and_schedule()

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={},
    )

    assert _running_card_ids(result.entries) == ["run.lthr_test"]
    assert result.backup_event_ids == frozenset({"ev_lthr_test"})


def test_non_backup_day_is_unchanged():
    block, schedule = _block_and_schedule()
    original = tuple(entry for entry in schedule if entry.day == 7)

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=7,
        attempt_statuses={},
    )

    assert result.entries == original
    assert result.backup_event_ids == frozenset()


def test_later_backup_stays_inactive_after_an_earlier_backup_is_valid():
    block, schedule = _block_and_schedule()
    event = block.measurement_events[0].model_copy(update={"backup_days": [8, 15]})
    block = block.model_copy(update={"measurement_events": [event]})

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=15,
        attempt_statuses={"ev_lthr_test": {1: "failed", 8: "valid"}},
    )

    assert _running_card_ids(result.entries) == ["run.tempo"]
    assert result.backup_event_ids == frozenset()


def test_multiple_events_activate_deterministically_on_their_own_backup_days():
    block, schedule = _block_and_schedule()
    second = MeasurementEvent(
        id="ev_second",
        card_id="run.easy_strides",
        estimand="secondary threshold",
        scheduled_day=9,
        backup_days=[15],
        required=True,
        on_all_missed="flag",
    )
    block = block.model_copy(update={"measurement_events": [*block.measurement_events, second]})

    first = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={},
    )
    second_result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=15,
        attempt_statuses={"ev_second": {9: "failed"}},
    )

    assert _running_card_ids(first.entries) == ["run.lthr_test"]
    assert first.backup_event_ids == frozenset({"ev_lthr_test"})
    assert _running_card_ids(second_result.entries) == ["run.easy_strides"]
    assert second_result.backup_event_ids == frozenset({"ev_second"})


def test_shared_card_events_keep_explicit_identity_across_two_backup_slots():
    block, schedule = _block_and_schedule()
    first_event = block.measurement_events[0]
    second_event = first_event.model_copy(
        update={"id": "ev_lthr_secondary", "on_all_missed": "flag"}
    )
    block = block.model_copy(update={"measurement_events": [first_event, second_event]})
    day_8_run = next(
        entry for entry in schedule if entry.day == 8 and entry.bundle_id == "running.v3"
    )
    second_slot = replace(
        day_8_run,
        slot="evening",
        assignment=day_8_run.assignment.model_copy(update={"slot": "evening"}),
    )
    schedule = [*schedule, second_slot]

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={},
    )

    assert _running_card_ids(result.entries) == ["run.lthr_test", "run.lthr_test"]
    assert [(activation.event_id, activation.entry_index) for activation in result.activations] == [
        ("ev_lthr_test", 0),
        ("ev_lthr_secondary", 3),
    ]


def test_backup_without_running_slot_preserves_other_bundles_and_does_not_substitute():
    block, schedule = _block_and_schedule()
    schedule_without_run = [
        entry for entry in schedule if not (entry.day == 8 and entry.bundle_id == "running.v3")
    ]
    original = tuple(entry for entry in schedule_without_run if entry.day == 8)

    result = resolve_measurement_day(
        block=block,
        schedule=schedule_without_run,
        day=8,
        attempt_statuses={},
    )
    after_final = resolve_measurement_day(
        block=block,
        schedule=schedule_without_run,
        day=9,
        attempt_statuses={},
    )

    assert result.entries == original
    assert result.backup_event_ids == frozenset()
    assert {entry.bundle_id for entry in result.entries} == {"strength.v3", "support.v3"}
    assert [action.model_dump() for action in after_final.required_actions] == [
        {"event_id": "ev_lthr_test", "action": "extend_block"}
    ]


def test_resolution_does_not_mutate_block_schedule_assignments_or_cards():
    block, schedule = _block_and_schedule()
    block_before = deepcopy(block.model_dump())
    schedule_before = deepcopy(schedule)

    result = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={},
    )

    assert block.model_dump() == block_before
    assert schedule == schedule_before
    assert result.entries is not schedule
    activated = next(entry for entry in result.entries if entry.bundle_id == "running.v3")
    assert activated.day == 8
    assert activated.slot == "morning"
    assert activated.assignment.day == 8
    assert activated.assignment.slot == "morning"
    assert activated.assignment.card_id == "run.lthr_test"


def test_required_action_appears_only_strictly_after_final_authored_attempt():
    block, schedule = _block_and_schedule()

    on_final_day = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=8,
        attempt_statuses={},
    )
    after_final_day = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=9,
        attempt_statuses={},
    )

    assert on_final_day.required_actions == ()
    assert [action.model_dump() for action in after_final_day.required_actions] == [
        {"event_id": "ev_lthr_test", "action": "extend_block"}
    ]


def test_required_action_is_suppressed_for_any_valid_attempt_or_optional_event():
    block, schedule = _block_and_schedule()
    event = block.measurement_events[0]

    valid = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=9,
        attempt_statuses={event.id: {1: "failed", 8: "valid"}},
    )
    optional_block = block.model_copy(
        update={"measurement_events": [event.model_copy(update={"required": False})]}
    )
    optional = resolve_measurement_day(
        block=optional_block,
        schedule=schedule,
        day=9,
        attempt_statuses={},
    )

    assert valid.required_actions == ()
    assert optional.required_actions == ()
