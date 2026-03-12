"""
Auth service: validates Telegram Web App initData and resolves the user role.
"""

import hashlib
import hmac
import json
import logging
from typing import Optional
from urllib.parse import parse_qsl, unquote

from backend.config import BOT_TOKEN, ROLE_EDITABLE_FIELDS, ROLE_LABELS_RU
from backend.models.schemas import MeResponse, UserInfo
from backend.services.sheets import get_user_info

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram initData verification
# ---------------------------------------------------------------------------

def verify_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Verify Telegram Mini App initData HMAC signature.

    Returns the parsed user dict on success, None on failure.
    Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
        ).digest()

        computed_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("initData hash mismatch")
            return None

        user_json = parsed.get("user", "{}")
        return json.loads(unquote(user_json))
    except Exception as exc:
        logger.error("initData verification error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

def resolve_user(telegram_id: int) -> MeResponse:
    """
    Look up the user in Google Sheets Настройки and return a MeResponse.
    Falls back to a safe no-access response if not found.
    """
    user = get_user_info(telegram_id)
    if not user or user.active.lower() not in ("1", "true", "yes", "да"):
        return MeResponse(
            telegram_id=telegram_id,
            full_name="Неизвестный",
            role="no_access",
            role_label_ru="Нет доступа",
            active=False,
            editable_fields=[],
        )

    role = user.role.strip()
    return MeResponse(
        telegram_id=telegram_id,
        full_name=user.full_name,
        role=role,
        role_label_ru=ROLE_LABELS_RU.get(role, role),
        active=True,
        editable_fields=ROLE_EDITABLE_FIELDS.get(role, []),
    )


def build_user_info_from_init_data(init_data: str) -> Optional[MeResponse]:
    """
    Full flow: verify initData → extract telegram_id → resolve role.
    Returns None if verification fails.
    """
    user_dict = verify_telegram_init_data(init_data)
    if not user_dict:
        return None
    tg_id = user_dict.get("id")
    if not tg_id:
        return None
    return resolve_user(int(tg_id))
