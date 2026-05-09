"""Card catalog use cases for artifact-authored card templates.

Artifacts own the `/api/cards` read surface because cards enter the system as
assistant-authored artifacts, while the live card records themselves are stored
through the routines repository.
"""

from __future__ import annotations

from app.domains.routines.contracts import CardTemplatesResponse
from app.domains.routines.dependencies import RoutineRepository


def list_cards(
    routines_repo: RoutineRepository,
    status: str | None = None,
) -> CardTemplatesResponse:
    """List live card templates, optionally filtered by runtime status."""
    cards = routines_repo.list_card_templates(status=status)
    return CardTemplatesResponse(cards=cards)
