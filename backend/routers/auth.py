import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.models.settings import UserAccessResponse
from backend.services.telegram_auth import (
    validate_telegram_init_data,
    extract_user_from_init_data,
)
from backend.services import settings_service
from backend.services.permissions import (
    get_editable_fields,
    NO_ACCESS_ROLE,
    ALLOWED_ROLES,
    ROLE_LABELS_RU,
    verify_role_password,
)
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Password-based Mini App auth
# ---------------------------------------------------------------------------

class RoleLoginRequest(BaseModel):
    role: str
    password: str


class RoleLoginResponse(BaseModel):
    success: bool
    role: str
    role_label: str


@router.post("/role-login", response_model=RoleLoginResponse)
async def role_login(body: RoleLoginRequest) -> RoleLoginResponse:
    """
    Validate a role+password pair for the Mini App login screen.

    The Mini App stores the returned role in localStorage so it persists
    across sessions.  No session token is issued on the backend side; the
    role is re-validated on every sensitive request via the role field in
    the request body or the X-User-Role header.
    """
    role = body.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    if not verify_role_password(role, body.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    return RoleLoginResponse(
        success=True,
        role=role,
        role_label=ROLE_LABELS_RU.get(role, role),
    )


# ---------------------------------------------------------------------------
# Telegram initData-based auth (existing endpoints, unchanged)
# ---------------------------------------------------------------------------

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
