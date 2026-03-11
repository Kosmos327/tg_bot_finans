import hashlib
import hmac
import json
import logging
from typing import Optional
from urllib.parse import unquote, parse_qsl

logger = logging.getLogger(__name__)


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validate Telegram WebApp initData according to Telegram documentation.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return False

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        computed_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_hash, received_hash)
    except Exception as exc:
        logger.warning("Failed to validate initData: %s", exc)
        return False


def extract_user_from_init_data(init_data: str) -> Optional[dict]:
    """Extract user info dict from Telegram initData string."""
    try:
        parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
        user_str = parsed.get("user")
        if user_str:
            return json.loads(user_str)
    except Exception as exc:
        logger.warning("Failed to extract user from initData: %s", exc)
    return None
