"""Simple in-memory cache, invalidated atomically on ingest.

Uses a generation counter so that computations started before an invalidation
cannot accidentally store stale results into the new generation.
"""

import threading
from collections.abc import Callable
from typing import Any

_lock = threading.Lock()
_generation = 0
_store: dict[str, tuple[int, Any]] = {}

# --- Cache keys (single source of truth) ---
DAILY_METRICS = "daily_metrics"
WELLNESS_ALL = "wellness_all"
SLEEP_ALL = "sleep_all"
HRV_ALL = "hrv_all"
SKIN_TEMP_ALL = "skin_temp_all"
AVAILABLE_DAYS = "available_days"
HR_ANALYSIS = "hr_analysis"
HRV_ANALYSIS = "hrv_analysis"


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


def cached[T](key: str, fn: Callable[[], T]) -> T:
    """Return cached value for *key*, or call *fn*, store, and return."""
    hit = get(key)
    if hit is not None:
        return hit
    gen = generation()
    result = fn()
    put(key, result, gen)
    return result
