"""Compile authored v3 assignments into a day/slot-ordered schedule.

The compiler resolves the ``full`` prescription used for static mileage and
time budgets. It emits no diagnostics: unknown card references are omitted
from the projection and reported by the L1 rule in ``validation.py``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from app.domains.training.contracts import (
    SlotName3,
    V3Assignment,
    V3Bundle,
    V3Card,
)

SLOT_HOUR: dict[str, int] = {"morning": 7, "midday": 13, "evening": 19}
_RUNNING_BUNDLE_ID = "running.v3"


def is_running_bundle(bundle_id: str) -> bool:
    """Return whether an authored bundle owns tracked-running cards."""
    return bundle_id == _RUNNING_BUNDLE_ID


@dataclass(frozen=True)
class CompiledEntry:
    """One scheduled occurrence: a card assigned to a bundle on a day/slot."""

    day: int
    slot: SlotName3
    bundle_id: str
    card: V3Card
    assignment: V3Assignment


def cards_by_id(bundles: list[V3Bundle]) -> dict[str, V3Card]:
    """Merge every bundle's cards into one id-keyed lookup.

    Card ids are unique across a valid bundle set and each card belongs to
    exactly one bundle.
    """
    return {card.id: card for bundle in bundles for card in bundle.cards}


def compile_schedule(bundles: list[V3Bundle]) -> list[CompiledEntry]:
    """Flatten every bundle's assignments into one day/slot-ordered schedule.

    Assignments referencing an unknown ``card_id`` are excluded here and
    reported by validation. Unrecognized slots sort last via the ``99``
    fallback, though typed input rejects them before compilation.
    """
    cards = cards_by_id(bundles)
    entries = [
        CompiledEntry(day=assignment.day, slot=assignment.slot, bundle_id=bundle.id,
                       card=cards[assignment.card_id], assignment=assignment)
        for bundle in bundles
        for assignment in bundle.assignments
        if assignment.card_id in cards
    ]
    entries.sort(key=lambda e: (e.day, SLOT_HOUR.get(e.slot, 99)))
    return entries


def seg_miles(prescription: dict[str, Any]) -> float:
    """Sum `distance_mi` across a (dict-form) segment prescription's segments."""
    return sum(s.get("distance_mi", 0) for s in prescription.get("segments", []))


def apply_patch(prescription: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    """Index-merge a variant's `prescription_patch` onto a base prescription dict.

    Only ``segments`` is patchable. Patch segment ``i`` is update-merged onto
    base segment ``i``; extra patch segments are ignored. Deep-copying keeps
    the authored prescription immutable and leaves strength prescriptions
    unchanged.
    """
    merged: dict[str, Any] = copy.deepcopy(prescription)
    base_segments = merged.get("segments", [])
    if patch and "segments" in patch:
        for i, patch_segment in enumerate(patch["segments"]):
            if i < len(base_segments):
                base_segments[i].update(patch_segment)
    return merged


def full_variant_prescription(entry: CompiledEntry) -> dict[str, Any]:
    """Resolve `entry`'s prescription as patched by its assignment's "full" variant.

    Static linting evaluates the full-volume path; runtime selection may choose
    another authored variant. L10 requires every assignment to declare
    ``full`` before this helper is used on valid content.
    """
    full = next(v for v in entry.assignment.variants if v.id == "full")
    base = entry.card.prescription.model_dump(exclude_none=True)
    return apply_patch(base, full.prescription_patch)


def entry_minutes(entry: CompiledEntry) -> float:
    """Estimate an entry's scheduled minutes, scaling run cards by distance.

    Cards with no `est_duration_min` contribute zero. Run cards (segment prescriptions with
    a positive base distance) scale their estimated duration by
    `full_mi / base_mi`, since the card's base prescription is a template and
    the "full" variant patch carries the day's actual distance.
    """
    card = entry.card
    if not card.est_duration_min:
        return 0.0
    base_minutes = card.est_duration_min
    base_prescription = card.prescription.model_dump(exclude_none=True)
    if "segments" in base_prescription and any(
        s.get("distance_mi") for s in base_prescription["segments"]
    ):
        base_mi = seg_miles(base_prescription)
        full_mi = seg_miles(full_variant_prescription(entry))
        if base_mi > 0 and full_mi > 0:
            return base_minutes * full_mi / base_mi
    return base_minutes


def week_of(day: int) -> int:
    """1-indexed week number for a 1-indexed block day (days 1-7 => week 1)."""
    return (day - 1) // 7 + 1


__all__ = [
    "SLOT_HOUR",
    "CompiledEntry",
    "apply_patch",
    "cards_by_id",
    "compile_schedule",
    "entry_minutes",
    "full_variant_prescription",
    "seg_miles",
    "week_of",
]
