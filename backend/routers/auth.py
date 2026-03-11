import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.models.settings import UserAccessResponse
from backend.services.telegram_auth import (
    validate_telegram_init_data,
    extract_user_from_init_data,
)
from backend.services import settings_service
from backend.services.permissions import get_editable_fields, NO_ACCESS_ROLE
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/validate")
async def validate_auth(
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Validate Telegram initData and return user info with role."""
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    token = settings.telegram_bot_token
    is_valid = validate_telegram_init_data(x_telegram_init_data, token)

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid initData")

    user = extract_user_from_init_data(x_telegram_init_data)
    user_id = str(user.get("id", "")) if user else ""

    role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
    full_name = settings_service.get_user_full_name(user_id) if user_id else ""

    return {
        "valid": True,
        "user": user,
        "role": role,
        "full_name": full_name,
        "editable_fields": sorted(get_editable_fields(role)),
    }


@router.get("/role", response_model=UserAccessResponse)
async def get_user_role(
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> UserAccessResponse:
    """Return the role and permissions for the authenticated user."""
    if not x_telegram_init_data:
        return UserAccessResponse(
            telegram_user_id="",
            role=NO_ACCESS_ROLE,
            active=False,
            editable_fields=[],
        )

    user = extract_user_from_init_data(x_telegram_init_data)
    user_id = str(user.get("id", "")) if user else ""

    role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
    active = settings_service.is_user_active(user_id) if user_id else False
    full_name = settings_service.get_user_full_name(user_id) if user_id else ""

    return UserAccessResponse(
        telegram_user_id=user_id,
        full_name=full_name,
        role=role,
        active=active,
        editable_fields=sorted(get_editable_fields(role)),
    )
