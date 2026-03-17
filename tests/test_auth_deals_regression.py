"""
Regression tests for targeted auth and deal-creation fixes.

Covers:
 - manager role-login with ekaterina/yulia (web auth)
 - manager login without selected_manager → fail
 - manager login with invalid selected_manager → fail
 - miniapp manual manager login uses PASSWORD_MANAGER_* (not ROLE_PASSWORD_MANAGER)
 - non-manager roles still use ROLE_PASSWORD_* successfully
 - /deals/create SQL: created_by_user_id is FIRST parameter in api_create_deal call
 - /deals/create: created_by_user_id and manager_id are NOT swapped
 - absence of ROLE_PASSWORD_MANAGER does not break manager auth
 - invalid ID_MANAGER_* env causes clear configuration error
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Set required env vars before any imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("WEBAPP_URL", "http://localhost")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")

# Role passwords for non-manager roles
os.environ.setdefault("ROLE_PASSWORD_OPERATIONS_DIRECTOR", "2")
os.environ.setdefault("ROLE_PASSWORD_ACCOUNTING", "3")
os.environ.setdefault("ROLE_PASSWORD_ADMIN", "12345")

# Manager-specific credentials
os.environ.setdefault("PASSWORD_MANAGER_EKATERINA", "ek_pass")
os.environ.setdefault("ID_MANAGER_EKATERINA", "10")
os.environ.setdefault("PASSWORD_MANAGER_YULIA", "yu_pass")
os.environ.setdefault("ID_MANAGER_YULIA", "20")

# ROLE_PASSWORD_MANAGER intentionally NOT set here — tests verify it is not required
# for manager login. If another test file set it earlier, clear it so we can test
# the "absent ROLE_PASSWORD_MANAGER" path.
os.environ.pop("ROLE_PASSWORD_MANAGER", None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from backend.main import app
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _mock_role(role_id=1, code="manager"):
    from app.database.models import Role
    r = Role()
    r.id = role_id
    r.code = code
    r.name = code
    return r


def _mock_app_user(user_id=5, telegram_id=123456):
    from app.database.models import AppUser
    u = AppUser()
    u.id = user_id
    u.telegram_id = telegram_id
    u.full_name = "Екатерина"
    u.username = "ekaterina"
    u.role_id = 1
    u.is_active = True
    return u


def _make_db_for_miniapp(role_obj, user_obj, manager_obj=None):
    """Return a mock AsyncSession for miniapp_login tests."""
    db = AsyncMock()
    db.flush = AsyncMock()
    added = []

    def fake_add(obj):
        added.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 99

    async def fake_refresh(obj):
        pass

    db.add.side_effect = fake_add
    db.refresh.side_effect = fake_refresh
    db._added = added

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
        return result

    db.execute = fake_execute
    return db


# ---------------------------------------------------------------------------
# 1. Web auth: /auth/role-login with manager role
# ---------------------------------------------------------------------------

class TestRoleLoginManagerAuth:
    """Regression tests for /auth/role-login manager paths."""

    def test_ekaterina_correct_password_returns_manager_id_10(self, client):
        resp = client.post("/auth/role-login", json={
            "role": "manager",
            "password": "ek_pass",
            "selected_manager": "ekaterina",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["role"] == "manager"
        assert data["manager_id"] == 10
        assert data["full_name"] == "Екатерина"
        assert data["user_id"] == 10

    def test_yulia_correct_password_returns_manager_id_20(self, client):
        resp = client.post("/auth/role-login", json={
            "role": "manager",
            "password": "yu_pass",
            "selected_manager": "yulia",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["role"] == "manager"
        assert data["manager_id"] == 20
        assert data["full_name"] == "Юлия"
        assert data["user_id"] == 20

    def test_manager_without_selected_manager_returns_400(self, client):
        resp = client.post("/auth/role-login", json={
            "role": "manager",
            "password": "ek_pass",
        })
        assert resp.status_code == 400

    def test_manager_with_invalid_selected_manager_returns_400(self, client):
        resp = client.post("/auth/role-login", json={
            "role": "manager",
            "password": "ek_pass",
            "selected_manager": "unknown_person",
        })
        assert resp.status_code == 400

    def test_manager_wrong_password_returns_401(self, client):
        resp = client.post("/auth/role-login", json={
            "role": "manager",
            "password": "wrong",
            "selected_manager": "ekaterina",
        })
        assert resp.status_code == 401

    def test_non_manager_roles_still_work(self, client):
        """Non-manager roles continue using ROLE_PASSWORD_* env vars."""
        resp = client.post("/auth/role-login", json={"role": "admin", "password": "12345"})
        assert resp.status_code == 200

        resp = client.post("/auth/role-login", json={"role": "accounting", "password": "3"})
        assert resp.status_code == 200

        resp = client.post("/auth/role-login", json={"role": "operations_director", "password": "2"})
        assert resp.status_code == 200

    def test_role_password_manager_absent_does_not_break_manager_auth(self, client):
        """ROLE_PASSWORD_MANAGER being absent/different must not prevent manager login.
        Manager auth uses PASSWORD_MANAGER_* vars, not the shared ROLE_PASSWORD_MANAGER."""
        # Patch settings to simulate ROLE_PASSWORD_MANAGER being absent while
        # manager-specific credentials are present — login must still succeed.
        from config.config import settings as web_settings
        with patch.object(web_settings, "password_manager_ekaterina", "ek_pass"), \
             patch.object(web_settings, "id_manager_ekaterina", "10"):
            resp = client.post("/auth/role-login", json={
                "role": "manager",
                "password": "ek_pass",
                "selected_manager": "ekaterina",
            })
        assert resp.status_code == 200
        assert resp.json()["manager_id"] == 10


# ---------------------------------------------------------------------------
# 2. Mini App manual login: manager path uses PASSWORD_MANAGER_* not ROLE_PASSWORD_MANAGER
# ---------------------------------------------------------------------------

class TestMiniappManagerAuth:
    """Regression tests for miniapp_login manager path."""

    @pytest.mark.asyncio
    async def test_ekaterina_correct_password_succeeds(self):
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        user = _mock_app_user()
        db = _make_db_for_miniapp(role_obj=role, user_obj=user)

        with patch.object(svc.settings, "password_manager_ekaterina", "ek_pass"), \
             patch.object(svc.settings, "id_manager_ekaterina", "10"):
            result = await svc.miniapp_login(
                db, 123456, "Екатерина", "ek", "manager", "ek_pass",
                selected_manager="ekaterina",
            )
        assert result["role"] == "manager"
        assert result["manager_id"] == 10
        assert result["full_name"] == "Екатерина"

    @pytest.mark.asyncio
    async def test_yulia_correct_password_succeeds(self):
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        user = _mock_app_user(telegram_id=111)
        db = _make_db_for_miniapp(role_obj=role, user_obj=user)

        with patch.object(svc.settings, "password_manager_yulia", "yu_pass"), \
             patch.object(svc.settings, "id_manager_yulia", "20"):
            result = await svc.miniapp_login(
                db, 111, "Юлия", "yu", "manager", "yu_pass",
                selected_manager="yulia",
            )
        assert result["role"] == "manager"
        assert result["manager_id"] == 20
        assert result["full_name"] == "Юлия"

    @pytest.mark.asyncio
    async def test_missing_selected_manager_raises_value_error(self):
        from backend.services.miniapp_auth_service import miniapp_login
        role = _mock_role()
        db = _make_db_for_miniapp(role_obj=role, user_obj=None)
        with pytest.raises(ValueError, match="selected_manager"):
            await miniapp_login(db, 999, "Test", "t", "manager", "any_pass")

    @pytest.mark.asyncio
    async def test_invalid_selected_manager_raises_value_error(self):
        from backend.services.miniapp_auth_service import miniapp_login
        role = _mock_role()
        db = _make_db_for_miniapp(role_obj=role, user_obj=None)
        with pytest.raises(ValueError, match="selected_manager"):
            await miniapp_login(db, 999, "Test", "t", "manager", "any_pass",
                                selected_manager="invalid_person")

    @pytest.mark.asyncio
    async def test_role_password_manager_not_used_for_manager_login(self):
        """Verify that ROLE_PASSWORD_MANAGER has no effect on manager auth."""
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        user = _mock_app_user()
        db = _make_db_for_miniapp(role_obj=role, user_obj=user)

        # Set a different ROLE_PASSWORD_MANAGER value that should NOT match
        with patch.object(svc.settings, "role_password_manager", "shared_mgr_pass"), \
             patch.object(svc.settings, "password_manager_ekaterina", "correct_ek"), \
             patch.object(svc.settings, "id_manager_ekaterina", "10"):
            # Using the specific manager password should succeed even if
            # ROLE_PASSWORD_MANAGER is set to something different
            result = await svc.miniapp_login(
                db, 123, "Екатерина", "ek", "manager", "correct_ek",
                selected_manager="ekaterina",
            )
            assert result["manager_id"] == 10

            # Using the ROLE_PASSWORD_MANAGER value should NOT work
            with pytest.raises(PermissionError):
                await svc.miniapp_login(
                    db, 123, "Екатерина", "ek", "manager", "shared_mgr_pass",
                    selected_manager="ekaterina",
                )

    @pytest.mark.asyncio
    async def test_non_manager_role_still_uses_role_password(self):
        from backend.services import miniapp_auth_service as svc
        role = _mock_role(role_id=3, code="accounting")
        user = _mock_app_user()
        db = _make_db_for_miniapp(role_obj=role, user_obj=user)

        with patch.object(svc.settings, "role_password_accounting", "acc_pass"):
            result = await svc.miniapp_login(
                db, 555, "Бухгалтер", None, "accounting", "acc_pass",
            )
        assert result["role"] == "accounting"
        assert "manager_id" not in result

    @pytest.mark.asyncio
    async def test_invalid_id_manager_env_raises_runtime_error(self):
        """If ID_MANAGER_* is not a valid integer, RuntimeError is raised."""
        from backend.services import miniapp_auth_service as svc
        role = _mock_role()
        db = _make_db_for_miniapp(role_obj=role, user_obj=None)

        with patch.object(svc.settings, "password_manager_ekaterina", "ek_pass"), \
             patch.object(svc.settings, "id_manager_ekaterina", "not_an_int"):
            with pytest.raises(RuntimeError, match="misconfigured"):
                await svc.miniapp_login(
                    db, 999, "Екатерина", "ek", "manager", "ek_pass",
                    selected_manager="ekaterina",
                )


# ---------------------------------------------------------------------------
# 3. SQL signature: /deals/create api_create_deal parameter order
# ---------------------------------------------------------------------------

class TestDealCreateSQLSignature:
    """
    Regression tests that prove created_by_user_id is first in the SQL call
    and that created_by_user_id and manager_id are NOT swapped.
    """

    def _extract_sql_and_params(self) -> tuple:
        """
        Run the create_deal endpoint with a mocked DB and capture the SQL
        text and params that were passed to call_sql_function_one.
        Returns (sql_text, params_dict).
        """
        import asyncio
        from fastapi.testclient import TestClient
        from backend.main import app

        captured = {}

        async def fake_call_sql_one(db, sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return {"id": 1, "status": "created"}

        async def fake_resolve_user(db, tid, init_data=None, role_header=None):
            return (42, "operations_director", "Director")

        with patch("backend.routers.deals_sql.call_sql_function_one", side_effect=fake_call_sql_one), \
             patch("backend.routers.deals_sql._resolve_user", side_effect=fake_resolve_user):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.post(
                    "/deals/create",
                    json={
                        "status_id": 1,
                        "business_direction_id": 2,
                        "client_id": 3,
                        "manager_id": 7,
                        "charged_with_vat": "1200.00",
                    },
                    headers={"X-User-Role": "operations_director"},
                )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        return captured.get("sql", ""), captured.get("params", {})

    def test_created_by_user_id_is_first_param_in_sql(self):
        sql, params = self._extract_sql_and_params()
        # created_by_user_id must appear before status_id in the SQL text
        assert ":created_by_user_id" in sql
        assert sql.index(":created_by_user_id") < sql.index(":status_id")

    def test_manager_id_is_after_client_id_in_sql(self):
        sql, params = self._extract_sql_and_params()
        # manager_id must come after client_id (per SQL signature)
        assert ":manager_id" in sql
        assert ":client_id" in sql
        assert sql.index(":client_id") < sql.index(":manager_id")

    def test_created_by_user_id_and_manager_id_not_swapped(self):
        sql, params = self._extract_sql_and_params()
        # created_by_user_id is first, manager_id is later — they must not be adjacent
        # in the wrong order (manager_id before created_by_user_id)
        cbuid_pos = sql.index(":created_by_user_id")
        mgrid_pos = sql.index(":manager_id")
        assert cbuid_pos < mgrid_pos, (
            "created_by_user_id must appear before manager_id in SQL text"
        )

    def test_charged_without_vat_not_in_sql(self):
        """charged_without_vat does not exist in the SQL function — must not be sent."""
        sql, params = self._extract_sql_and_params()
        assert ":charged_without_vat" not in sql

    def test_params_include_created_by_user_id(self):
        sql, params = self._extract_sql_and_params()
        assert "created_by_user_id" in params

    def test_created_by_user_id_is_authenticated_user_id(self):
        """created_by_user_id must be the auth context user_id (42), not manager_id (7)."""
        sql, params = self._extract_sql_and_params()
        assert params.get("created_by_user_id") == 42
        assert params.get("manager_id") == 7

    def test_created_by_user_id_none_for_web_mode(self):
        """When user_id is not an integer (web mode), created_by_user_id is None."""
        import asyncio
        from fastapi.testclient import TestClient
        from backend.main import app

        captured = {}

        async def fake_call_sql_one(db, sql, params):
            captured["params"] = params
            return {"id": 1}

        async def fake_resolve_user(db, tid, init_data=None, role_header=None):
            # Web-mode: user_id is empty string, not an int
            return ("", "operations_director", "")

        with patch("backend.routers.deals_sql.call_sql_function_one", side_effect=fake_call_sql_one), \
             patch("backend.routers.deals_sql._resolve_user", side_effect=fake_resolve_user):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.post(
                    "/deals/create",
                    json={
                        "status_id": 1,
                        "business_direction_id": 2,
                        "client_id": 3,
                        "manager_id": 7,
                        "charged_with_vat": "1200.00",
                    },
                    headers={"X-User-Role": "operations_director"},
                )

        assert resp.status_code == 200
        assert captured.get("params", {}).get("created_by_user_id") is None
