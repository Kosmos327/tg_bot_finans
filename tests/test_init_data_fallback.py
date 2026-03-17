"""
Tests for X-Telegram-Init-Data fallback authentication in protected SQL endpoints.

These tests verify that when X-Telegram-Id header is absent but a valid
X-Telegram-Init-Data header is present, the endpoints can still authenticate
the user by validating the HMAC and looking up app_users.

Covers:
  - miniapp_auth_service.resolve_user_from_init_data
  - deals_sql._resolve_user (initData fallback path)
  - expenses_sql._resolve_user (initData fallback path)
  - billing_sql._resolve_user (initData fallback path)
  - month_close._resolve_user (initData fallback path)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

import pytest

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_bot_token_123")
os.environ.setdefault("WEBAPP_URL", "http://localhost")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")


# ---------------------------------------------------------------------------
# Helpers: build a valid Telegram initData string
# ---------------------------------------------------------------------------

def _build_init_data(bot_token: str, user_id: int, first_name: str = "Test") -> str:
    """Build a valid Telegram WebApp initData string with proper HMAC."""
    user_obj = json.dumps({"id": user_id, "first_name": first_name, "is_bot": False})
    auth_date = int(time.time())

    raw_fields = {
        "auth_date": str(auth_date),
        "user": user_obj,
    }

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(raw_fields.items()))

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

    fields = dict(raw_fields)
    fields["hash"] = computed_hash
    return urlencode(fields)


# ---------------------------------------------------------------------------
# Mocked DB helpers (reused from test_miniapp_auth pattern)
# ---------------------------------------------------------------------------

def _mock_app_user(telegram_id=123456, role_id=1, is_active=True):
    from app.database.models import AppUser
    u = AppUser()
    u.id = 10
    u.telegram_id = telegram_id
    u.full_name = "Test User"
    u.username = "testuser"
    u.role_id = role_id
    u.is_active = is_active
    return u


def _mock_role(role_id=1, code="manager"):
    from app.database.models import Role
    r = Role()
    r.id = role_id
    r.code = code
    r.name = code.capitalize()
    return r


def _make_db(user=None, role=None):
    """Return a mock AsyncSession that returns user/role on execute."""
    db = AsyncMock()

    async def fake_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt)
        if "app_users" in stmt_str:
            result.scalar_one_or_none.return_value = user
        elif "roles" in stmt_str:
            result.scalar_one_or_none.return_value = role
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db.execute = fake_execute
    return db


# ---------------------------------------------------------------------------
# Tests: resolve_user_from_init_data
# ---------------------------------------------------------------------------

class TestResolveUserFromInitData:
    """Unit tests for miniapp_auth_service.resolve_user_from_init_data."""

    BOT_TOKEN = "test_bot_token_123"

    @pytest.mark.asyncio
    async def test_returns_no_access_when_init_data_empty(self):
        from backend.services.miniapp_auth_service import resolve_user_from_init_data
        from backend.services.permissions import NO_ACCESS_ROLE
        db = _make_db()
        user_id, role, full_name = await resolve_user_from_init_data(db, "")
        assert role == NO_ACCESS_ROLE
        assert user_id is None

    @pytest.mark.asyncio
    async def test_returns_no_access_when_hmac_invalid(self):
        from backend.services.miniapp_auth_service import resolve_user_from_init_data
        from backend.services.permissions import NO_ACCESS_ROLE
        db = _make_db()
        # Build initData with wrong token so HMAC is invalid
        bad_init_data = _build_init_data("wrong_token_xyz", user_id=111)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await resolve_user_from_init_data(db, bad_init_data)
        assert role == NO_ACCESS_ROLE

    @pytest.mark.asyncio
    async def test_returns_no_access_when_user_not_in_app_users(self):
        from backend.services.miniapp_auth_service import resolve_user_from_init_data
        from backend.services.permissions import NO_ACCESS_ROLE
        db = _make_db(user=None)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=999)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await resolve_user_from_init_data(db, init_data)
        assert role == NO_ACCESS_ROLE

    @pytest.mark.asyncio
    async def test_returns_user_on_valid_init_data(self):
        from backend.services.miniapp_auth_service import resolve_user_from_init_data
        from backend.services.permissions import NO_ACCESS_ROLE
        user = _mock_app_user(telegram_id=123456, role_id=1)
        role_obj = _mock_role(role_id=1, code="manager")
        db = _make_db(user=user, role=role_obj)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=123456)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await resolve_user_from_init_data(db, init_data)
        assert role == "manager"
        assert user_id == 10
        assert full_name == "Test User"

    @pytest.mark.asyncio
    async def test_returns_no_access_when_token_not_set(self):
        from backend.services.miniapp_auth_service import resolve_user_from_init_data
        from backend.services.permissions import NO_ACCESS_ROLE
        db = _make_db()
        init_data = _build_init_data(self.BOT_TOKEN, user_id=123456)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""
            user_id, role, full_name = await resolve_user_from_init_data(db, init_data)
        assert role == NO_ACCESS_ROLE


# ---------------------------------------------------------------------------
# Tests: _resolve_user in SQL routers (initData fallback path)
# ---------------------------------------------------------------------------

class TestDealsResolveUserFallback:
    """Tests for deals_sql._resolve_user with initData fallback."""

    BOT_TOKEN = "test_bot_token_123"

    @pytest.mark.asyncio
    async def test_falls_back_to_init_data_when_no_telegram_id(self):
        from backend.routers.deals_sql import _resolve_user
        from backend.services.permissions import NO_ACCESS_ROLE
        user = _mock_app_user(telegram_id=123456, role_id=1)
        role_obj = _mock_role(role_id=1, code="manager")
        db = _make_db(user=user, role=role_obj)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=123456)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await _resolve_user(
                db, x_telegram_id=None, x_telegram_init_data=init_data
            )
        assert role == "manager"
        assert user_id == 10

    @pytest.mark.asyncio
    async def test_prefers_telegram_id_over_init_data(self):
        """X-Telegram-Id should be used when present, even if initData is also provided."""
        from backend.routers.deals_sql import _resolve_user
        user = _mock_app_user(telegram_id=123456, role_id=1)
        role_obj = _mock_role(role_id=1, code="manager")
        db = _make_db(user=user, role=role_obj)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=999999)  # different id in initData
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await _resolve_user(
                db, x_telegram_id="123456", x_telegram_init_data=init_data
            )
        # Should resolve via X-Telegram-Id (123456), not via initData (999999)
        assert role == "manager"
        assert user_id == 10

    @pytest.mark.asyncio
    async def test_returns_no_access_when_both_absent(self):
        from backend.routers.deals_sql import _resolve_user
        from backend.services.permissions import NO_ACCESS_ROLE
        db = _make_db()
        user_id, role, full_name = await _resolve_user(
            db, x_telegram_id=None, x_telegram_init_data=None
        )
        assert role == NO_ACCESS_ROLE
        assert user_id is None


class TestExpensesResolveUserFallback:
    """Tests for expenses_sql._resolve_user with initData fallback."""

    BOT_TOKEN = "test_bot_token_123"

    @pytest.mark.asyncio
    async def test_falls_back_to_init_data(self):
        from backend.routers.expenses_sql import _resolve_user
        user = _mock_app_user(telegram_id=77777, role_id=3)
        role_obj = _mock_role(role_id=3, code="accounting")
        db = _make_db(user=user, role=role_obj)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=77777)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await _resolve_user(
                db, x_telegram_id=None, x_telegram_init_data=init_data
            )
        assert role == "accounting"


class TestBillingResolveUserFallback:
    """Tests for billing_sql._resolve_user with initData fallback."""

    BOT_TOKEN = "test_bot_token_123"

    @pytest.mark.asyncio
    async def test_falls_back_to_init_data(self):
        from backend.routers.billing_sql import _resolve_user
        user = _mock_app_user(telegram_id=88888, role_id=3)
        role_obj = _mock_role(role_id=3, code="accounting")
        db = _make_db(user=user, role=role_obj)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=88888)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await _resolve_user(
                db, x_telegram_id=None, x_telegram_init_data=init_data
            )
        assert role == "accounting"


class TestMonthCloseResolveUserFallback:
    """Tests for month_close._resolve_user with initData fallback."""

    BOT_TOKEN = "test_bot_token_123"

    @pytest.mark.asyncio
    async def test_falls_back_to_init_data(self):
        from backend.routers.month_close import _resolve_user
        user = _mock_app_user(telegram_id=99999, role_id=4)
        role_obj = _mock_role(role_id=4, code="admin")
        db = _make_db(user=user, role=role_obj)
        init_data = _build_init_data(self.BOT_TOKEN, user_id=99999)
        with patch("backend.services.miniapp_auth_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = self.BOT_TOKEN
            user_id, role, full_name = await _resolve_user(
                db, x_telegram_id=None, x_telegram_init_data=init_data
            )
        assert role == "admin"
