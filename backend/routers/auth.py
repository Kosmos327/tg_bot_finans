"""Auth router – /me endpoint."""

from fastapi import APIRouter, Depends

from backend.dependencies import get_current_user
from backend.models.schemas import MeResponse

router = APIRouter(prefix="/me", tags=["auth"])


@router.get("", response_model=MeResponse)
def me(current_user: MeResponse = Depends(get_current_user)) -> MeResponse:
    """Return the current user's role metadata."""
    return current_user
