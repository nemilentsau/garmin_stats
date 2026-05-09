"""Card catalog use cases owned by artifact-authored card templates."""

from __future__ import annotations

from app.domains.routines.contracts import CardTemplatesResponse
from app.domains.routines.dependencies import RoutineRepository


def list_cards(
    routines_repo: RoutineRepository,
    status: str | None = None,
) -> CardTemplatesResponse:
    cards = routines_repo.list_card_templates(status=status)
    return CardTemplatesResponse(cards=cards)
