"""Settings router – user/role configuration."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.config import ROLE_MANAGER, ROLE_ACCOUNTANT
from backend.dependencies import get_current_user, require_active_user
from backend.models.schemas import MeResponse
from backend.services.sheets import get_active_users, get_all_settings_users

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=List[Dict[str, Any]])
def get_settings(current_user: MeResponse = Depends(get_current_user)):
    require_active_user(current_user)
    # Only ops director and head_of_sales can see all settings
    if current_user.role in (ROLE_MANAGER, ROLE_ACCOUNTANT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра настроек",
        )
    users = get_active_users()
    return [u.model_dump() for u in users]
