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
    Regression tests that prove create_deal passes params as a plain dict
    with :name placeholders, guaranteeing that SQLAlchemy's text() binding
    routes each value to the correct SQL function argument by name.

    Root cause of the 500 crash: params was a plain Python list, which
    exec_driver_sql treated as an executemany batch, causing:
      "List argument must consist only of tuples or dictionaries"

    Fix: params is now a plain dict with 19 named keys matching :name
    placeholders in the SQL string.

    Parameter mapping (dict key → SQL placeholder → PostgreSQL argument):
      created_by_user_id  → :created_by_user_id  → p_created_by_user_id
      status_id           → :status_id            → p_status_id
      business_direction_id → :business_direction_id → p_business_direction_id
      client_id           → :client_id            → p_client_id
      manager_id          → :manager_id           → p_manager_id
      charged_with_vat    → :charged_with_vat     → p_charged_with_vat
      vat_type_id         → :vat_type_id          → p_vat_type_id
      vat_rate            → :vat_rate             → p_vat_rate
      paid                → :paid                 → p_paid
      project_start_date  → :project_start_date   → p_project_start_date
      project_end_date    → :project_end_date     → p_project_end_date
      act_date            → :act_date             → p_act_date
      variable_expense_1_without_vat → :variable_expense_1_without_vat
      variable_expense_2_without_vat → :variable_expense_2_without_vat
      production_expense_without_vat → :production_expense_without_vat
      manager_bonus_percent → :manager_bonus_percent → p_manager_bonus_percent
      source_id           → :source_id            → p_source_id
      document_link       → :document_link        → p_document_link
      comment             → :comment              → p_comment
    """

    _TOTAL_PARAMS = 19

    def _extract_sql_and_params(self) -> tuple:
        """
        Run the create_deal endpoint with a mocked DB and capture the SQL
        text and params dict that were passed to call_sql_function_one.
        Returns (sql_text, params_dict).
        """
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

    def test_sql_uses_named_placeholders(self):
        """SQL must use :name style placeholders, not positional $N style."""
        import re
        sql, params = self._extract_sql_and_params()
        assert ":created_by_user_id" in sql, "SQL must contain :created_by_user_id named placeholder"
        assert ":comment" in sql, "SQL must contain :comment named placeholder"
        assert "$1" not in sql, (
            "SQL must NOT contain $1 positional placeholder — use :name style instead"
        )
        assert "$19" not in sql, (
            "SQL must NOT contain $19 positional placeholder — use :name style instead"
        )

    def test_params_is_a_dict(self):
        """Params must be a plain dict (not a list) to prevent exec_driver_sql 500 crash."""
        sql, params = self._extract_sql_and_params()
        assert isinstance(params, dict), (
            f"params must be a plain dict, got {type(params).__name__} — "
            "passing a list causes: 'List argument must consist only of tuples or dictionaries'"
        )

    def test_params_has_exact_count(self):
        """Params dict must contain exactly 19 keys matching the SQL function signature."""
        sql, params = self._extract_sql_and_params()
        assert len(params) == self._TOTAL_PARAMS, (
            f"Expected {self._TOTAL_PARAMS} params, got {len(params)}: {list(params.keys())}"
        )

    def test_created_by_user_id_is_in_params(self):
        """created_by_user_id must be a key in the params dict."""
        sql, params = self._extract_sql_and_params()
        assert isinstance(params, dict)
        assert "created_by_user_id" in params, "created_by_user_id key missing from params dict"
        assert params["created_by_user_id"] == 42, (
            f"params['created_by_user_id'] should be 42, got {params.get('created_by_user_id')!r}"
        )

    def test_client_id_is_in_params(self):
        """client_id must be a key in the params dict with the submitted value."""
        sql, params = self._extract_sql_and_params()
        assert isinstance(params, dict)
        assert "client_id" in params, "client_id key missing from params dict"
        assert params["client_id"] == 3, (
            f"params['client_id'] should be 3, got {params.get('client_id')!r}"
        )

    def test_manager_id_is_in_params(self):
        """manager_id must be a key in the params dict with the submitted value."""
        sql, params = self._extract_sql_and_params()
        assert isinstance(params, dict)
        assert "manager_id" in params, "manager_id key missing from params dict"
        assert params["manager_id"] == 7, (
            f"params['manager_id'] should be 7, got {params.get('manager_id')!r}"
        )

    def test_created_by_user_id_and_manager_id_not_swapped(self):
        """created_by_user_id and manager_id must not be swapped in the params dict."""
        sql, params = self._extract_sql_and_params()
        assert isinstance(params, dict)
        assert params["created_by_user_id"] == 42, "created_by_user_id must be 42"
        assert params["manager_id"] == 7, "manager_id must be 7"

    def test_charged_without_vat_not_in_params(self):
        """p_charged_without_vat does not exist in the SQL function — must not be in params."""
        sql, params = self._extract_sql_and_params()
        assert "charged_without_vat" not in params, (
            "charged_without_vat must not be in params — it is not a SQL function argument"
        )
        assert len(params) == self._TOTAL_PARAMS, (
            "Params dict has wrong length — charged_without_vat may have been injected"
        )

    def test_created_by_user_id_none_for_web_mode(self):
        """When user_id is not an integer (web mode), params['created_by_user_id'] is None."""
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
        params = captured.get("params", {})
        assert isinstance(params, dict), "params must be a plain dict"
        assert params.get("created_by_user_id") is None, (
            f"params['created_by_user_id'] should be None in web mode, "
            f"got {params.get('created_by_user_id')!r}"
        )

    def test_client_id_is_present_and_not_none_in_params(self):
        """
        Regression: client_id must be a key in the params dict and must be non-None.
        This guards against the original bug where client_id was saved as NULL.
        """
        submitted_client_id = 3  # value sent in _extract_sql_and_params payload
        sql, params = self._extract_sql_and_params()
        assert isinstance(params, dict), "params must be a plain dict"
        assert "client_id" in params, "client_id key missing from params dict"
        assert params["client_id"] is not None, (
            "params['client_id'] is None — deal would be saved with NULL client"
        )
        assert params["client_id"] == submitted_client_id, (
            f"params['client_id'] should be {submitted_client_id}, "
            f"got {params['client_id']!r}"
        )
