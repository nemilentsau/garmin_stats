"""Dependencies consumed by training import, activation, and capture use cases.

Import/activation (`application/imports.py`) and per-occurrence capture
logging both persist through this single protocol. The concrete SQLite
adapter (`adapters.py`) owns the single-active-block/bundle retirement
invariant and transaction boundaries; this module only describes the shape
callers depend on.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.training.contracts import (
    StoredBlock,
    StoredBundle,
    StoredLibrary,
    StoredRegistry,
    TrainingCardLog,
)


class TrainingRepository(Protocol):
    """Persistence dependency for v3 training import, activation, and capture logs."""

    def active_block(self) -> StoredBlock | None: ...

    def bundles_for(self, bundle_ids: str | list[str]) -> list[StoredBundle]:
        """Load active bundles by id (accepts one id or a list of ids)."""
        ...

    def registry(self) -> StoredRegistry | None: ...

    def library(self) -> StoredLibrary | None: ...

    def save_import(
        self,
        *,
        block: StoredBlock,
        bundles: list[StoredBundle],
        registry: StoredRegistry,
        library: StoredLibrary,
    ) -> None:
        """Retire any previously active block/bundles and persist the new active set.

        Implementations must run this as one transaction: activation is
        single-shot, so partial writes are never observable.
        """
        ...

    def card_log(self, date: str, occurrence_key: str) -> TrainingCardLog | None: ...

    def card_logs_for(self, date: str) -> list[TrainingCardLog]: ...

    def card_logs_before(self, date: str) -> list[TrainingCardLog]:
        """Load every capture log recorded strictly before `date`.

        The history read behind the `last`-logged load anchor
        (`application/read_models.py`'s `last_logged_for`).
        """
        ...

    def upsert_card_log(self, log: TrainingCardLog) -> None: ...
