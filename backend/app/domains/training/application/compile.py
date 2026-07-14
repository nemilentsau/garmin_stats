"""Schedule compiler ported from the block0 linter's compile section.

Owns the part of `docs/routine-pivot/block0/linter.py` (lines 29-89) that
turns a set of v3 bundles into a flat, day/slot-ordered schedule and resolves
the per-entry "full" variant prescription used to estimate run mileage and
scheduled minutes. This module works from Task 1's typed contracts
(`V3Bundle`, `V3Card`, `V3Assignment`) instead of raw dicts, but the merge and
scaling arithmetic is a verbatim port: `apply_patch` mirrors the linter's
`apply_full_patch` index-merge semantics, and `entry_minutes` mirrors its
distance-based minute-scaling heuristic exactly.

This module deliberately does not evaluate any L1-L12 rule and never raises or
records a lint diagnostic. `compile_schedule` silently drops assignments that
reference an unknown `card_id` — the same outcome as the linter's `err(...);
continue` — but leaves emitting that error to `validation.py`, which has its
own unknown-card-reference check (the residual part of L1 not already
subsumed by Task 1's typed contracts). Keeping compilation diagnostic-free
lets `validation.py` be the single place that decides what is an error versus
a warning.
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

    Card ids are unique across the bundle set in valid v3 content (each card
    belongs to exactly one bundle); this mirrors the linter's single global
    `cards` dict built by iterating all bundles.
    """
    return {card.id: card for bundle in bundles for card in bundle.cards}


def compile_schedule(bundles: list[V3Bundle]) -> list[CompiledEntry]:
    """Flatten every bundle's assignments into one day/slot-ordered schedule.

    Assignments referencing an unknown `card_id` are silently excluded (the
    linter's `err("L1", ...); continue`, minus the error emission — see the
    module docstring). Sort key matches the linter: `(day, SLOT_HOUR[slot])`,
    with unrecognized slots sorted last via the `99` fallback.
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

    Verbatim port of the linter's `apply_full_patch` merge step: only the
    `segments` key is patched, patch segment `i` is `dict.update`-merged onto
    base segment `i`, and patch segments beyond the base segment count are
    ignored. `prescription` is deep-copied first (matching the linter's
    `json.loads(json.dumps(...))` round trip) so a base lacking a `segments`
    key at all — a strength card's `{"exercises": [...]}` — comes back
    unchanged rather than gaining a spurious empty one.
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

    Mirrors the linter's `apply_full_patch(card, assign)`: block0 lint always
    validates the schedule at the "full" variant's volume, since day-to-day
    variant selection is a runtime concern outside the block's static
    contract. Raises `StopIteration` if the assignment has no "full" variant —
    the same failure the linter's `next(...)` would raise, and L10 already
    checks every assignment declares one.
    """
    full = next(v for v in entry.assignment.variants if v.id == "full")
    base = entry.card.prescription.model_dump(exclude_none=True)
    return apply_patch(base, full.prescription_patch)


def entry_minutes(entry: CompiledEntry) -> float:
    """Estimate an entry's scheduled minutes, scaling run cards by distance.

    Verbatim port of the linter's `entry_minutes`: cards with no
    `est_duration_min` contribute zero. Run cards (segment prescriptions with
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
