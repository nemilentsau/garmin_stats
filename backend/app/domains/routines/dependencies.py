"""Ports consumed by routine application use cases.

Application modules depend on these protocols instead of concrete persistence or
cross-domain services. Bootstrap code wires the SQLite adapter and optional
observers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.domains.routines.contracts import (
    CardLog,
    CardOverride,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
)

CardTemplateDependencyActivator = Callable[[str], None]


class TodayCardLogObserver(Protocol):
    """Observer notified after a Today card log changes for a date."""

    def sync_for_date(self, *, date: str) -> None: ...


class RoutineRepository(Protocol):
    """Persistence port for compiled routines, cards, overrides, and logs."""

    def save_card_template(self, card: CardTemplate) -> None: ...
    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]: ...
    def get_routine(self, routine_id: str) -> RoutineSchedule | None: ...
    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]: ...
    def list_card_templates(self, *, status: str | None = None) -> list[CardTemplate]: ...
    def get_card_template(self, card_id: str) -> CardTemplate | None: ...
    def list_card_overrides_range(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> list[CardOverride]: ...
    def list_card_logs(self, *, date: str | None = None) -> list[CardLog]: ...
    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]: ...
    def save_card_log(self, log: CardLog) -> None: ...
    def save_routine(self, routine: RoutineSchedule) -> None: ...
    def save_routine_with_assignments(
        self,
        *,
        routine: RoutineSchedule,
        assignments: list[RoutineAssignment],
    ) -> None: ...
    def replace_assignments(
        self,
        *,
        routine_id: str,
        assignments: list[RoutineAssignment],
    ) -> None: ...
