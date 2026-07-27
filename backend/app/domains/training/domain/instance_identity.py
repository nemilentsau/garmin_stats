"""Deterministic ownership identities for imported training programs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_IDENTITY_VERSION = 1
_PROGRAM_INSTANCE_ID = re.compile(r"^training_v[1-9][0-9]*_[0-9a-f]{64}$")


def program_instance_id(
    *,
    block: dict[str, Any],
    bundles: list[dict[str, Any]],
    registry: dict[str, Any],
    library: dict[str, Any],
    schedule_start: str,
) -> str:
    """Hash one complete authored artifact set and its selected start date.

    JSON object key order and upload file order are deliberately irrelevant.
    Bundle order is supplied by the block's authored ``bundle_ids`` ordering,
    so the same validated import always resolves to the same identity.
    """
    canonical = json.dumps(
        {
            "identity_version": _IDENTITY_VERSION,
            "schedule_start": schedule_start,
            "block": block,
            "bundles": bundles,
            "registry": registry,
            "library": library,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"training_v3_{hashlib.sha256(canonical).hexdigest()}"


def occurrence_id(program_instance_id: str, occurrence_key: str) -> str:
    """Namespace an authored occurrence key for durable storage/correlation."""
    return f"{program_instance_id}:{occurrence_key}"


def is_occurrence_id(value: object) -> bool:
    """Return whether a value already carries a versioned program namespace."""
    if not isinstance(value, str):
        return False
    instance_id, separator, occurrence_key = value.partition(":")
    return bool(
        separator
        and occurrence_key
        and _PROGRAM_INSTANCE_ID.fullmatch(instance_id)
    )


def card_log_id(program_instance_id: str, date: str, occurrence_key: str) -> str:
    """Return the durable primary key for one program-owned capture log."""
    return f"{program_instance_id}:{date}:{occurrence_key}"
