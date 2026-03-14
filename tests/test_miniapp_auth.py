"""
Tests for Mini App authentication:
  - POST /auth/miniapp-login endpoint validation logic
  - miniapp_auth_service: role resolution, password validation
  - deals router: user resolution from X-Telegram-Id header
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Set up required env vars before any imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("WEBAPP_URL", "http://localhost")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")


# ---------------------------------------------------------------------------
# miniapp_auth_service: _verify_role_password
# ---------------------------------------------------------------------------


class TestVerifyRolePassword:
    """Tests for _verify_role_password using patched settings."""

    def _call(self, role: str, password: str, env_passwords: dict) -> bool:
        from backend.services import miniapp_auth_service as svc
        with patch.object(svc.settings, "role_password_manager", env_passwords.get("manager", "")):
            with patch.object(svc.settings, "role_password_operations_director", env_passwords.get("operations_director", "")):
                with patch.object(svc.settings, "role_password_accounting", env_passwords.get("accounting", "")):
                    with patch.object(svc.settings, "role_password_admin", env_passwords.get("admin", "")):
                        return svc._verify_role_password(role, password)

    def test_correct_manager_password(self):
        assert self._call("manager", "secret_manager", {"manager": "secret_manager"}) is True

    def test_correct_admin_password(self):
        assert self._call("admin", "secret_admin", {"admin": "secret_admin"}) is True

    def test_wrong_password_returns_false(self):
        assert self._call("manager", "wrong", {"manager": "correct"}) is False

    def test_unknown_role_returns_false(self):
        assert self._call("ghost_role", "any", {}) is False

    def test_empty_env_var_returns_false(self):
        assert self._call("manager", "", {"manager": ""}) is False


# ---------------------------------------------------------------------------
# miniapp_auth_service: miniapp_login (async, with mocked DB)
# ---------------------------------------------------------------------------


def _mock_role(role_id=1, code="manager", name="Менеджер"):
    from app.database.models import Role
    r = Role()
    r.id = role_id
    r.code = code
    r.name = name
    return r


def _mock_app_user(telegram_id=123, role_id=1, is_active=True):
    from app.database.models import AppUser
    u = AppUser()
    u.id = 10
    u.telegram_id = telegram_id
    u.full_name = "Test User"
    u.username = "testuser"
    u.role_id = role_id
    u.is_active = is_active
    return u


def _make_db_with_lookup(role_obj, user_obj, manager_obj):
    """Return a mock AsyncSession where execute() dispatches by table name."""
    db = AsyncMock()
    db.flush = AsyncMock()

    added_objects = []

    def fake_add(obj):
        added_objects.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 99

    async def fake_refresh(obj):
        pass

    db.add.side_effect = fake_add
    db.refresh.side_effect = fake_refresh
    db._added = added_objects

    call_index = [0]

    async def fake_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt)
        if "roles" in stmt_str:
            result.scalar_one_or_none.return_value = role_obj
        elif "app_users" in stmt_str:
            result.scalar_one_or_none.return_value = user_obj
        elif "managers" in stmt_str:
            result.scalar_one_or_none.return_value = manager_obj
        else:
            result.scalar_one_or_none.return_value = None
        call_index[0] += 1
        return result

    db.execute = fake_execute
    return db


class TestMiniappLogin:
    """Unit tests for miniapp_login() with a fully mocked AsyncSession."""

    def _patch_password(self, role="manager", password="secret_manager"):
        """Context manager that patches the relevant settings attribute."""
        from backend.services import miniapp_auth_service as svc
        attr_map = {
            "manager": "role_password_manager",
            "operations_director": "role_password_operations_director",
            "accounting": "role_password_accounting",
            "admin": "role_password_admin",
        }
        attr = attr_map.get(role, "role_password_manager")
        return patch.object(svc.settings, attr, password)

    @pytest.mark.asyncio
    async def test_invalid_role_raises_value_error(self):
        from backend.services.miniapp_auth_service import miniapp_login
        db = _make_db_with_lookup(role_obj=None, user_obj=None, manager_obj=None)
        with pytest.raises(ValueError, match="does not exist"):
            await miniapp_login(db, 123, "Test", "user", "ghost_role", "pass")

    @pytest.mark.asyncio
    async def test_wrong_password_raises_permission_error(self):
        from backend.services.miniapp_auth_service import miniapp_login
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        db = _make_db_with_lookup(role_obj=role, user_obj=None, manager_obj=None)
        with patch.object(svc.settings, "role_password_manager", "correct_password"):
            with pytest.raises(PermissionError, match="Invalid password"):
                await miniapp_login(db, 123, "Test", "user", "manager", "wrong_pass")

    @pytest.mark.asyncio
    async def test_successful_login_creates_new_user(self):
        from backend.services.miniapp_auth_service import miniapp_login
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        db = _make_db_with_lookup(role_obj=role, user_obj=None, manager_obj=None)

        with patch.object(svc.settings, "role_password_manager", "secret_manager"):
            result = await miniapp_login(db, 123456, "Ivan Petrov", "ivan", "manager", "secret_manager")

        assert result["telegram_id"] == 123456
        assert result["full_name"] == "Ivan Petrov"
        assert result["username"] == "ivan"
        assert result["role"] == "manager"
        assert "user_id" in result
        # Both app_user and manager should have been added
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_successful_login_updates_existing_user(self):
        from backend.services.miniapp_auth_service import miniapp_login
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        existing_user = _mock_app_user(telegram_id=123456)
        existing_user.full_name = "Old Name"
        db = _make_db_with_lookup(role_obj=role, user_obj=existing_user, manager_obj=None)

        with patch.object(svc.settings, "role_password_manager", "secret_manager"):
            result = await miniapp_login(db, 123456, "New Name", "newuser", "manager", "secret_manager")

        assert result["full_name"] == "New Name"
        assert result["username"] == "newuser"
        # Only manager was added (user was updated in place)
        assert db.add.call_count == 1

    @pytest.mark.asyncio
    async def test_non_manager_role_does_not_create_manager(self):
        from backend.services.miniapp_auth_service import miniapp_login
        from backend.services import miniapp_auth_service as svc
        role = _mock_role(role_id=3, code="accounting", name="Бухгалтерия")
        db = _make_db_with_lookup(role_obj=role, user_obj=None, manager_obj=None)

        with patch.object(svc.settings, "role_password_accounting", "secret_accounting"):
            await miniapp_login(db, 789, "Anna", None, "accounting", "secret_accounting")

        # Only app_user should be added; manager auto-binding skipped for non-manager
        assert db.add.call_count == 1


# ---------------------------------------------------------------------------
# miniapp_auth_service: get_user_by_telegram_id
# ---------------------------------------------------------------------------


class TestGetUserByTelegramId:
    def _make_db(self, user=None, role=None):
        db = AsyncMock()
        call_count = [0]

        async def fake_execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "app_users" in stmt_str:
                result.scalar_one_or_none.return_value = user
            elif "roles" in stmt_str:
                result.scalar_one_or_none.return_value = role
            else:
                result.scalar_one_or_none.return_value = None
            call_count[0] += 1
            return result

        db.execute = fake_execute
        return db

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        from backend.services.miniapp_auth_service import get_user_by_telegram_id
        db = self._make_db(user=None)
        result = await get_user_by_telegram_id(db, 42)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_inactive(self):
        from backend.services.miniapp_auth_service import get_user_by_telegram_id
        inactive = _mock_app_user(is_active=False)
        db = self._make_db(user=inactive)
        result = await get_user_by_telegram_id(db, 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_when_active(self):
        from backend.services.miniapp_auth_service import get_user_by_telegram_id
        active = _mock_app_user(telegram_id=999, is_active=True)
        role = _mock_role()
        db = self._make_db(user=active, role=role)
        result = await get_user_by_telegram_id(db, 999)
        assert result is not None
        assert result.telegram_id == 999

