"""Shared lowercase tokenization for assistant alias matching.

``normalize_alias`` defines the canonical form written to (and queried from)
``assistant_memory_records.alias_normalized``. Writers and lookup callers must
use the same normalization or saved aliases become unreachable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_LOWERCASE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Return lowercase alphanumeric tokens from ``text`` in order."""
    return _LOWERCASE_TOKEN_PATTERN.findall(text.lower())


def normalize_alias(value: str | None) -> str | None:
    """Return the space-joined token form, or ``None`` if no tokens remain."""
    if value is None:
        return None
    tokens = tokenize(value)
    if not tokens:
        return None
    return " ".join(tokens)


def dedupe_strings(values: Iterable[str]) -> list[str]:
    """Return ``values`` with duplicates removed, preserving first-seen order."""
    return list(dict.fromkeys(values))
