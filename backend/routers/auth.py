import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
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
from backend.services.miniapp_auth_service import miniapp_login, get_user_by_telegram_id, get_role_code
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Mini App login — supports two modes:
#   1. Auto-login (init_data only): validates Telegram initData signature and
#      returns the existing app_users record for the caller. No password needed.
#   2. Manual login (telegram_id + full_name + selected_role + password):
#      original flow — creates/updates the app_users record.
# ---------------------------------------------------------------------------


class MiniAppLoginRequest(BaseModel):
    # Auto-login path: provide only init_data (Telegram WebApp initData string)
    init_data: Optional[str] = None
    # Manual login path: all fields below are required when init_data is absent
    telegram_id: Optional[int] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    selected_role: Optional[str] = None
    password: Optional[str] = None


class MiniAppLoginResponse(BaseModel):
    user_id: int
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    role: str


@router.post("/miniapp-login", response_model=MiniAppLoginResponse)
async def miniapp_login_endpoint(
    body: MiniAppLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> MiniAppLoginResponse:
    """
    Mini App login endpoint.

    **Auto-login path** (``init_data`` provided):
    Validates the Telegram WebApp ``initData`` HMAC signature, extracts the
    Telegram user ID, and returns the existing ``app_users`` record for that
    user.  No role password is required — the cryptographic signature of the
    Telegram platform is the authentication proof.  Returns 403 if the
    signature is invalid or if the user has no ``app_users`` record yet (they
    must complete the one-time manual registration first).

    **Manual login path** (``telegram_id`` + ``full_name`` + ``selected_role``
    + ``password`` provided):
    Validates the role password, creates or updates the ``app_users`` record,
    and auto-binds a manager record when role is ``'manager'``.

    Returns user info on success.
    """
    if body.init_data:
        # ------------------------------------------------------------------
        # Auto-login: validate initData signature, look up existing user
        # ------------------------------------------------------------------
        logger.info("POST /auth/miniapp-login (auto-login via initData)")

        token = settings.telegram_bot_token
        is_valid = validate_telegram_init_data(body.init_data, token)
        if not is_valid:
            logger.warning("miniapp-login auto-login: invalid initData signature")
            raise HTTPException(status_code=403, detail="Invalid Telegram initData signature")

        user_dict = extract_user_from_init_data(body.init_data)
        if not user_dict:
            logger.warning("miniapp-login auto-login: cannot extract user from initData")
            raise HTTPException(status_code=403, detail="Cannot extract user from initData")

        telegram_id = user_dict.get("id")
        if not telegram_id:
            logger.warning("miniapp-login auto-login: no id field in initData user")
            raise HTTPException(status_code=403, detail="No telegram_id in initData")

        app_user = await get_user_by_telegram_id(db, int(telegram_id))
        if app_user is None:
            logger.info(
                "miniapp-login auto-login: telegram_id=%s not found in app_users",
                telegram_id,
            )
            raise HTTPException(
                status_code=403,
                detail="User not registered. Please log in with your role and password first.",
            )

        role = await get_role_code(db, app_user.role_id)
        if role is None:
            logger.error(
                "miniapp-login auto-login: role_id=%s not found for app_user_id=%s",
                app_user.role_id,
                app_user.id,
            )
            raise HTTPException(status_code=500, detail="User role not found")

        logger.info(
            "miniapp-login auto-login success: telegram_id=%s app_user_id=%s role=%r",
            telegram_id,
            app_user.id,
            role,
        )
        return MiniAppLoginResponse(
            user_id=app_user.id,
            telegram_id=app_user.telegram_id,
            full_name=app_user.full_name,
            username=app_user.username,
            role=role,
        )

    # ------------------------------------------------------------------
    # Manual login: telegram_id + full_name + selected_role + password
    # ------------------------------------------------------------------
    if body.telegram_id is None or not body.full_name or not body.selected_role or not body.password:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'init_data' for auto-login, or 'telegram_id', 'full_name', 'selected_role', and 'password' for manual login.",
        )

    logger.info(
        "POST /auth/miniapp-login: telegram_id=%s selected_role=%r",
        body.telegram_id,
        body.selected_role,
    )

    try:
        result = await miniapp_login(
            db=db,
            telegram_id=body.telegram_id,
            full_name=body.full_name,
            username=body.username,
            selected_role=body.selected_role,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Invalid password for role '{body.selected_role}'",
        ) from exc

    return MiniAppLoginResponse(**result)


# ---------------------------------------------------------------------------
# Password-based Mini App auth (legacy role-only login)
# ---------------------------------------------------------------------------

class RoleLoginRequest(BaseModel):
    role: str
    password: str
    selected_manager: Optional[str] = None  # "ekaterina" or "yulia" (manager role only)


class RoleLoginResponse(BaseModel):
    success: bool
    role: str
    role_label: str
    user_id: Optional[int] = None
    full_name: Optional[str] = None
    manager_id: Optional[int] = None
    telegram_id: Optional[int] = None


@router.post("/role-login", response_model=RoleLoginResponse)
async def role_login(body: RoleLoginRequest) -> RoleLoginResponse:
    """
    Validate a role+password pair for web (browser) mode login.
    No Telegram ID is required.

    For the ``manager`` role, ``selected_manager`` must be provided
    (``"ekaterina"`` or ``"yulia"``); the password is validated against
    the corresponding ``PASSWORD_MANAGER_*`` environment variable and the
    ``manager_id`` is returned from the corresponding ``ID_MANAGER_*`` variable.

    For all other roles the password is validated against the shared
    ``ROLE_PASSWORD_*`` environment variable.

    Returns user info (including ``manager_id`` for managers) on success.
    """
    role = body.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    user_id: Optional[int] = None
    full_name: Optional[str] = None
    manager_id: Optional[int] = None

    if role == "manager":
        selected_manager = (body.selected_manager or "").strip().lower()
        if selected_manager == "ekaterina":
            expected_password = settings.password_manager_ekaterina
            manager_full_name = "Екатерина"
            manager_id_str = settings.id_manager_ekaterina
        elif selected_manager == "yulia":
            expected_password = settings.password_manager_yulia
            manager_full_name = "Юлия"
            manager_id_str = settings.id_manager_yulia
        else:
            raise HTTPException(
                status_code=400,
                detail="Unknown manager. Select Екатерина or Юлия.",
            )

        if not expected_password or body.password != expected_password:
            raise HTTPException(status_code=401, detail="Invalid password")

        full_name = manager_full_name
        try:
            manager_id = int(manager_id_str) if manager_id_str else None
        except (ValueError, TypeError):
            logger.error(
                "Invalid manager ID configured for %r: %r. "
                "Set ID_MANAGER_%s to a valid integer.",
                selected_manager,
                manager_id_str,
                selected_manager.upper(),
            )
            raise HTTPException(
                status_code=500,
                detail="Manager ID is misconfigured. Contact your administrator.",
            )
        user_id = manager_id
    else:
        if not verify_role_password(role, body.password):
            raise HTTPException(status_code=401, detail="Invalid password")

    return RoleLoginResponse(
        success=True,
        role=role,
        role_label=ROLE_LABELS_RU.get(role, role),
        user_id=user_id,
        full_name=full_name,
        manager_id=manager_id,
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

