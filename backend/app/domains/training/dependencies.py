"""Dependencies consumed by training import, activation, and capture use cases.

Import/activation (`application/imports.py`) and per-occurrence capture
logging both persist through this single protocol. The concrete SQLite
adapter (`adapters.py`) owns the single-active-block/bundle retirement
invariant and transaction boundaries; this module only describes the shape
callers depend on.

`RunActivityReadPort` is a second, unrelated dependency: the read-only seam
`application/read_models.py`'s run<->prescription association policy uses to
see tracked runs. `training` must never import `garmin_analytics`/
`garmin_health` (see `CHARTER.md`), so this Protocol is implemented entirely
outside the slice — `bootstrap/run_activity_port.py` adapts the
`garmin_analytics` runs repository to it, and `bootstrap/container.py` wires
the concrete instance in. Association is Today-only: `get_training_today`
takes this port as an optional parameter and threads it down to the read
model's card projection; `get_training_schedule_window` never receives one.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.training.contracts import (
    StoredBlock,
    StoredBundle,
    StoredLibrary,
    StoredRegistry,
    TrainingCardLog,
    TrainingRunActivitySummary,
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


class RunActivityReadPort(Protocol):
    """Read-only view of tracked runs for one date; implemented outside training.

    The single seam through which the Today read model's run<->prescription
    association policy sees tracked-run data. Every field on the returned
    `TrainingRunActivitySummary` is already training-local and imperial —
    the implementation owns any unit conversion, so nothing here or in
    `application/read_models.py` ever imports a garmin contract or unit.
    """

    def runs_for_date(self, date: str) -> list[TrainingRunActivitySummary]: ...
