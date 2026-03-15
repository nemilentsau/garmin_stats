"""Card template HTTP routes."""

from fastapi import APIRouter

from ..models import CardTemplatesResponse
from ..services.training_specs import list_cards

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("", response_model=CardTemplatesResponse)
def get_cards(status: str | None = None):
    """Return compiled live card templates."""
    return list_cards(status=status)
