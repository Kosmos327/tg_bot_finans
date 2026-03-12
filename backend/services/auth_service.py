"""
Telegram WebApp initData authentication service.

Validates the `initData` string sent by the Telegram WebApp client
using HMAC-SHA256 as described in the official Telegram documentation:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import logging
from urllib.parse import unquote, parse_qsl

from config.config import settings

logger = logging.getLogger(__name__)


def _build_data_check_string(params: dict[str, str]) -> str:
    """Build the data-check string by sorting keys (excluding 'hash')."""
    pairs = sorted(
        (k, v) for k, v in params.items() if k != "hash"
    )
    return "\n".join(f"{k}={v}" for k, v in pairs)


def verify_init_data(init_data: str) -> dict:
    """
    Verify Telegram WebApp initData and return the parsed payload.

    Args:
        init_data: URL-encoded initData string from Telegram WebApp.

    Returns:
        Parsed dict of the initData fields including 'user'.

    Raises:
        ValueError: If the signature is invalid or data is malformed.
    """
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as exc:
        raise ValueError(f"Malformed initData: {exc}") from exc

    received_hash = params.get("hash", "")
    if not received_hash:
        raise ValueError("initData does not contain 'hash' field")

    data_check_string = _build_data_check_string(params)

    # HMAC key = HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=settings.telegram_bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Invalid initData signature")

    # Parse nested 'user' JSON string if present
    if "user" in params:
        try:
            params["user"] = json.loads(unquote(params["user"]))
        except json.JSONDecodeError:
            pass

    return params
