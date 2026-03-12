import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.services.telegram_auth import (
    validate_telegram_init_data,
    extract_user_from_init_data,
)
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/validate")
async def validate_auth(
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Validate Telegram initData and return user info."""
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    token = settings.telegram_bot_token
    is_valid = validate_telegram_init_data(x_telegram_init_data, token)

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid initData")

    user = extract_user_from_init_data(x_telegram_init_data)
    return {"valid": True, "user": user}
