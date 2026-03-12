"""Journal router – audit log."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from backend.config import ROLE_MANAGER
from backend.dependencies import get_current_user, require_active_user
from backend.models.schemas import MeResponse
from backend.services.sheets import get_recent_journal

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/recent", response_model=List[Dict[str, Any]])
def recent_journal(
    limit: int = Query(default=50, le=200),
    current_user: MeResponse = Depends(get_current_user),
):
    require_active_user(current_user)
    # Manager cannot view the journal
    if current_user.role == ROLE_MANAGER:
        return []
    entries = get_recent_journal(limit=limit)
    return [e.model_dump() for e in entries]
