"""Card template HTTP routes."""

from fastapi import APIRouter

from app.bootstrap.container import build_container
from app.domains.artifacts.application.artifacts import list_cards
from app.domains.routines.contracts import CardTemplatesResponse

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("", response_model=CardTemplatesResponse)
def get_cards(status: str | None = None):
    """Return compiled live card templates."""
    return list_cards(build_container().routines_repo, status=status)
