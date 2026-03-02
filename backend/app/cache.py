"""Simple in-memory cache, invalidated atomically on ingest.

Uses a generation counter so that computations started before an invalidation
cannot accidentally store stale results into the new generation.
"""

import threading
from typing import Any

_lock = threading.Lock()
_generation = 0
_store: dict[str, tuple[int, Any]] = {}


def generation() -> int:
    """Return the current cache generation (snapshot for put)."""
    return _generation


def get(key: str) -> Any | None:
    """Return cached value if it matches the current generation, else None."""
    entry = _store.get(key)
    if entry is not None and entry[0] == _generation:
        return entry[1]
    return None


def put(key: str, value: Any, gen: int) -> None:
    """Store *value* only if *gen* still matches the current generation."""
    with _lock:
        if gen == _generation:
            _store[key] = (gen, value)


def invalidate() -> None:
    """Bump the generation and clear all entries."""
    global _generation
    with _lock:
        _generation += 1
        _store.clear()
