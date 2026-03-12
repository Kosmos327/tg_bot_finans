"""
Shared FastAPI dependency: extract and validate current user from initData header.
"""

from fastapi import Header, HTTPException, status

from backend.models.schemas import MeResponse
from backend.services.auth import build_user_info_from_init_data, resolve_user


def get_current_user(x_init_data: str = Header(default="")) -> MeResponse:
    """
    FastAPI dependency.

    Clients must pass the Telegram initData in the ``X-Init-Data`` header.
    In development / testing, if BOT_TOKEN is empty the header is parsed
    without cryptographic verification and the telegram_id is read directly.
    """
    if not x_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Init-Data header missing",
        )

    me = build_user_info_from_init_data(x_init_data)
    if me is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram initData",
        )
    return me


def require_active_user(me: MeResponse) -> MeResponse:
    if not me.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа",
        )
    return me
