"""Shared lowercase tokenization for assistant alias matching.

``normalize_alias`` defines the canonical form written to (and queried from)
``assistant_memory_records.alias_normalized``. Writers and lookup callers must
use the same normalization or saved aliases become unreachable.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable

_LOWERCASE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

EXPERIMENT_REVIEW_TERMS: frozenset[str] = frozenset({"experiment", "trial", "study"})
"""Singular lexical terms that signal an experiment-review intent or context."""

PLURAL_EXPERIMENT_REVIEW_TERMS: frozenset[str] = frozenset(
    {"experiments", "trials", "studies"}
)
"""Plural lexical terms that signal an experiment-review intent or context."""

ALL_EXPERIMENT_REVIEW_TERMS: frozenset[str] = (
    EXPERIMENT_REVIEW_TERMS | PLURAL_EXPERIMENT_REVIEW_TERMS
)
"""All lexical terms that signal an experiment-review intent or context."""

ENTITY_RESOLUTION_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "does",
        "far",
        "how",
        "like",
        "look",
        "our",
        "so",
        "the",
    }
)
"""Common query words ignored by assistant entity matching."""

ALIAS_MIN_TOKENS = 2
ALIAS_MAX_TOKENS = 6
"""Alias phrase token limits used by both alias writers and lookup callers."""

MEMORY_RECALL_LIMIT = 5
"""Prompt-recall and evidence-bundle cap on assistant memory records per turn."""


def tokenize(text: str) -> list[str]:
    """Return lowercase alphanumeric tokens from ``text`` in order."""
    return _LOWERCASE_TOKEN_PATTERN.findall(text.lower())


def token_set(
    text: str,
    *,
    stop_words: Collection[str] = frozenset(),
) -> set[str]:
    """Return lowercase tokens with optional stop words removed."""
    return {token for token in tokenize(text) if token not in stop_words}


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
