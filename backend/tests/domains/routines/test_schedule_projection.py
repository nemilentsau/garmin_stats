"""Tests that define the shared routine schedule projection contract."""

import pytest

from app.domains.routines.contracts import CardOverride
from tests._routines_helpers import (
    activate_routine_card as _activate_card,
)
from tests._routines_helpers import (
    activate_routine_spec as _activate_routine,
)
from tests._routines_helpers import (
    get_schedule_window,
    persist_card_override,
)
from tests._routines_helpers import (
    routine_assignment_spec as _assignment,
)


def _days_by_date(window):
    return {day.date: day for day in window.days}


def _all_occurrences(window):
    return [occurrence for day in window.days for occurrence in day.occurrences]


class TestScheduleProjection:
    def test_two_week_window_includes_empty_days_and_day_based_matches(self):
        """Day 1 and day 8 should both appear in a 14-day window starting on the start date."""
        _activate_card("card-weekly", name="Weekly Card", slot_default="evening")
        _activate_routine(
            "routine-weekly",
            assignments=[
                _assignment(
                    "assignment-day1",
                    card_template_id="card-weekly",
                    day=1,
                    slot="evening",
                    position=20,
                ),
                _assignment(
                    "assignment-day8",
                    card_template_id="card-weekly",
                    day=8,
                    slot="evening",
                    position=20,
                ),
            ],
        )

        window = get_schedule_window("2026-03-02")
        days = _days_by_date(window)
        occurrence_dates = [
            occurrence.date
            for occurrence in _all_occurrences(window)
            if occurrence.card_template_id == "card-weekly"
        ]

        assert window.start_date == "2026-03-02"
        assert window.end_date == "2026-03-15"
        assert len(window.days) == 14
        assert window.days[0].date == "2026-03-02"
        assert window.days[-1].date == "2026-03-15"
        assert occurrence_dates == ["2026-03-02", "2026-03-09"]
        assert days["2026-03-03"].occurrences == []

    def test_inactive_routines_do_not_contribute_occurrences(self):
        _activate_card("card-active", name="Active Card")
        _activate_card("card-paused", name="Paused Card")
        _activate_routine(
            "routine-active",
            assignments=[
                _assignment(
                    "assignment-active",
                    card_template_id="card-active",
                    day=1,
                    slot="morning",
                    position=10,
                )
            ],
            status="active",
        )
        _activate_routine(
            "routine-paused",
            assignments=[
                _assignment(
                    "assignment-paused",
                    card_template_id="card-paused",
                    day=1,
                    slot="morning",
                    position=20,
                )
            ],
            status="paused",
        )

        window = get_schedule_window("2026-03-02")
        card_ids = {occurrence.card_template_id for occurrence in _all_occurrences(window)}

        assert card_ids == {"card-active"}

    def test_start_and_end_dates_clip_occurrences_at_boundaries(self):
        _activate_card("card-start-boundary", name="Start Boundary Card")
        _activate_card("card-end-inclusive", name="End Inclusive Card")
        _activate_card("card-end-clipped", name="End Clipped Card")

        # Routine starting on day 10 of the window (2026-03-11)
        _activate_routine(
            "routine-start-boundary",
            start_date="2026-03-11",
            assignments=[
                _assignment(
                    "assignment-start-boundary",
                    card_template_id="card-start-boundary",
                    day=1,
                    slot="morning",
                    position=10,
                )
            ],
        )
        # end_date 2026-03-11 — day 3 and day 10 should both appear
        _activate_routine(
            "routine-end-inclusive",
            start_date="2026-03-02",
            end_date="2026-03-11",
            assignments=[
                _assignment(
                    "assignment-end-day3",
                    card_template_id="card-end-inclusive",
                    day=3,
                    slot="midday",
                    position=10,
                ),
                _assignment(
                    "assignment-end-day10",
                    card_template_id="card-end-inclusive",
                    day=10,
                    slot="midday",
                    position=10,
                ),
            ],
        )
        # Routine with end_date 2026-03-10 — day 3 appears, day 10 clipped
        _activate_routine(
            "routine-end-clipped",
            start_date="2026-03-02",
            end_date="2026-03-10",
            assignments=[
                _assignment(
                    "assignment-clip-day3",
                    card_template_id="card-end-clipped",
                    day=3,
                    slot="evening",
                    position=10,
                ),
                _assignment(
                    "assignment-clip-day10",
                    card_template_id="card-end-clipped",
                    day=10,
                    slot="evening",
                    position=10,
                ),
            ],
        )

        window = get_schedule_window("2026-03-02")
        dates_by_card = {
            card_id: [
                occurrence.date
                for occurrence in _all_occurrences(window)
                if occurrence.card_template_id == card_id
            ]
            for card_id in {
                "card-start-boundary",
                "card-end-inclusive",
                "card-end-clipped",
            }
        }

        assert dates_by_card["card-start-boundary"] == ["2026-03-11"]
        assert dates_by_card["card-end-inclusive"] == ["2026-03-04", "2026-03-11"]
        assert dates_by_card["card-end-clipped"] == ["2026-03-04"]

    def test_overlapping_routines_both_appear_on_the_same_day(self):
        _activate_card("card-overlap-a", name="Overlap A")
        _activate_card("card-overlap-b", name="Overlap B")
        _activate_routine(
            "routine-overlap-a",
            assignments=[
                _assignment(
                    "assignment-overlap-a",
                    card_template_id="card-overlap-a",
                    day=1,
                    slot="morning",
                    position=10,
                )
            ],
        )
        _activate_routine(
            "routine-overlap-b",
            assignments=[
                _assignment(
                    "assignment-overlap-b",
                    card_template_id="card-overlap-b",
                    day=1,
                    slot="morning",
                    position=20,
                )
            ],
        )

        window = get_schedule_window("2026-03-02")
        day_occurrences = _days_by_date(window)["2026-03-02"].occurrences

        assert {occurrence.routine_id for occurrence in day_occurrences} == {
            "routine-overlap-a",
            "routine-overlap-b",
        }

    def test_occurrences_are_sorted_by_slot_then_position_within_a_day(self):
        _activate_card("card-morning-late", name="Morning Late")
        _activate_card("card-morning-early", name="Morning Early")
        _activate_card("card-evening", name="Evening Card", slot_default="evening")
        _activate_routine(
            "routine-ordered",
            assignments=[
                _assignment(
                    "assignment-morning-late",
                    card_template_id="card-morning-late",
                    day=1,
                    slot="morning",
                    position=30,
                ),
                _assignment(
                    "assignment-evening",
                    card_template_id="card-evening",
                    day=1,
                    slot="evening",
                    position=5,
                ),
                _assignment(
                    "assignment-morning-early",
                    card_template_id="card-morning-early",
                    day=1,
                    slot="morning",
                    position=10,
                ),
            ],
        )

        window = get_schedule_window("2026-03-02")
        ordered = [
            (occurrence.slot, occurrence.position, occurrence.card_template_id)
            for occurrence in _days_by_date(window)["2026-03-02"].occurrences
        ]

        assert ordered == [
            ("morning", 10, "card-morning-early"),
            ("morning", 30, "card-morning-late"),
            ("evening", 5, "card-evening"),
        ]

    def test_persisted_add_and_hide_overrides_are_applied_to_schedule_window(self):
        _activate_card("card-main", name="Main Card", slot_default="evening")
        _activate_card("card-extra", name="Extra Card", slot_default="morning")
        _activate_routine(
            "routine-main",
            assignments=[
                _assignment(
                    "assignment-main",
                    card_template_id="card-main",
                    day=1,
                    slot="evening",
                    position=20,
                )
            ],
        )

        window_before = get_schedule_window("2026-03-02")
        scheduled_occurrence = _days_by_date(window_before)["2026-03-02"].occurrences[0]

        persist_card_override(
            CardOverride(
                id="override-extra",
                date="2026-03-02",
                action="add",
                card_template_id="card-extra",
                slot="morning",
                position=5,
            )
        )
        persist_card_override(
            CardOverride(
                id="override-hide-main",
                date="2026-03-02",
                action="hide",
                target_occurrence_key=scheduled_occurrence.occurrence_key,
            )
        )

        window_after = get_schedule_window("2026-03-02")
        day_occurrences = _days_by_date(window_after)["2026-03-02"].occurrences

        assert [occurrence.card_template_id for occurrence in day_occurrences] == ["card-extra"]
        assert day_occurrences[0].occurrence_key == "override:add:override-extra:2026-03-02"
        assert day_occurrences[0].source_kind == "override_add"
        assert day_occurrences[0].schedule_override_action == "add"
        assert day_occurrences[0].routine_id is None

    def test_persisted_replace_override_is_applied_to_schedule_window(self):
        _activate_card("card-main", name="Main Card", slot_default="evening")
        _activate_card("card-extra", name="Extra Card", slot_default="morning")
        _activate_routine(
            "routine-main",
            assignments=[
                _assignment(
                    "assignment-main",
                    card_template_id="card-main",
                    day=1,
                    slot="evening",
                    position=20,
                )
            ],
        )

        window_before = get_schedule_window("2026-03-02")
        scheduled_occurrence = _days_by_date(window_before)["2026-03-02"].occurrences[0]

        persist_card_override(
            CardOverride(
                id="override-replace-main",
                date="2026-03-02",
                action="replace",
                target_occurrence_key=scheduled_occurrence.occurrence_key,
                card_template_id="card-extra",
            )
        )

        window_after = get_schedule_window("2026-03-02")
        day_occurrences = _days_by_date(window_after)["2026-03-02"].occurrences

        assert [occurrence.card_template_id for occurrence in day_occurrences] == ["card-extra"]
        assert (
            day_occurrences[0].occurrence_key
            == "override:replace:override-replace-main:2026-03-02"
        )
        assert day_occurrences[0].source_kind == "override_replace"
        assert day_occurrences[0].schedule_override_action == "replace"
        assert day_occurrences[0].routine_id == "routine-main"
        assert day_occurrences[0].target_occurrence_key == scheduled_occurrence.occurrence_key

    def test_replace_override_without_target_occurrence_is_ignored(self):
        _activate_card("card-extra", name="Extra Card", slot_default="morning")

        persist_card_override(
            CardOverride(
                id="override-replace-missing",
                date="2026-03-02",
                action="replace",
                target_occurrence_key="scheduled:missing:2026-03-02",
                card_template_id="card-extra",
            )
        )

        window = get_schedule_window("2026-03-02", duration_days=1)

        assert window.days[0].occurrences == []

    def test_invalid_start_date_raises_value_error(self):
        with pytest.raises(ValueError):
            get_schedule_window("03-02-2026")
