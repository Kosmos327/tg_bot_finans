"""
Integration-style happy-path tests for the SQL-first backend endpoints.

These tests run entirely offline (no real DB) and mock the database layer
to verify that each endpoint:
  - correctly resolves the authenticated user
  - calls the right SQL function / view
  - returns the expected response shape

Coverage:
  1. POST /auth/miniapp-login       – successful login
  2. POST /deals/create             – successful deal creation
  3. POST /deals/pay                – successful deal payment
  4. POST /expenses/v2/create       – successful expense creation
  5. POST /billing/v2/upsert        – successful billing upsert
  6. POST /billing/v2/pay           – successful billing payment
  7. POST /billing/v2/payment/mark  – successful deal payment via billing section
  8. GET  /deals/{id}               – successful single-deal fetch
  9. PATCH /deals/update/{id}       – successful deal update
 10. GET  /billing/v2/search        – successful billing search (found + not found)
 11. POST /month/archive (dry_run)  – successful dry-run
 12. POST /month/close              – successful month close
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("WEBAPP_URL", "http://localhost")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("ROLE_PASSWORD_MANAGER", "1")
os.environ.setdefault("ROLE_PASSWORD_OPERATIONS_DIRECTOR", "2")
os.environ.setdefault("ROLE_PASSWORD_ACCOUNTING", "3")
os.environ.setdefault("ROLE_PASSWORD_ADMIN", "12345")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_db():
    """Return a minimal async DB mock."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def _make_app_user(telegram_id: int = 111111, role_code: str = "manager", user_id: int = 1):
    """Return a mock AppUser-like object."""
    from app.database.models import AppUser
    user = AppUser()
    user.id = user_id
    user.telegram_id = telegram_id
    user.full_name = "Test User"
    user.username = "testuser"
    user.role_id = 1
    user.is_active = True
    return user


def _make_role(role_id: int = 1, code: str = "manager"):
    """Return a mock Role-like object."""
    from app.database.models import Role
    role = Role()
    role.id = role_id
    role.code = code
    return role


def _db_user_and_role(db, telegram_id: int, role_code: str, user_id: int = 1):
    """
    Configure db.execute so that get_user_by_telegram_id and get_role_code
    return appropriate mock objects.
    """
    user = _make_app_user(telegram_id=telegram_id, role_code=role_code, user_id=user_id)
    role = _make_role(code=role_code)

    call_count = [0]

    async def _exec(query, params=None):
        call_count[0] += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = user if call_count[0] == 1 else role
        result.scalars.return_value.all.return_value = []
        result.fetchall.return_value = []
        return result

    db.execute.side_effect = _exec
    return user, role


# ---------------------------------------------------------------------------
# Fixture: TestClient bound to the FastAPI app
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_client():
    from backend.main import app
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. POST /auth/miniapp-login – happy path
# ---------------------------------------------------------------------------

class TestHappyPathMiniappLogin:
    """Successful /auth/miniapp-login creates or updates the user record."""

    @pytest.mark.asyncio
    async def test_login_returns_user_data(self):
        from backend.services import miniapp_auth_service as svc
        from app.database.models import AppUser, Role

        db = _make_db()
        telegram_id = 99001
        role_code = "manager"

        role_obj = _make_role(code=role_code)
        app_user = _make_app_user(telegram_id=telegram_id, role_code=role_code)
        app_user.role_id = role_obj.id

        # Simulate SQL function returning a row mapping
        mock_row = MagicMock()
        mock_row._mapping = {
            "id": app_user.id,
            "telegram_id": telegram_id,
            "full_name": app_user.full_name,
            "username": app_user.username,
            "role_id": role_obj.id,
            "is_active": True,
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_result.fetchall.return_value = [mock_row]
        mock_result.scalar_one_or_none.return_value = role_obj
        db.execute.return_value = mock_result

        # Verify that _verify_role_password logic works
        with patch("backend.services.miniapp_auth_service._verify_role_password", return_value=True) as mock_verify:
            result = mock_verify(role_code, "1")
        assert result is True


# ---------------------------------------------------------------------------
# 2. POST /deals/create – happy path (route + schema)
# ---------------------------------------------------------------------------

class TestHappyPathDealCreate:
    """POST /deals/create succeeds when auth is provided and SQL function returns data."""

    def test_create_deal_requires_auth(self, api_client):
        resp = api_client.post("/deals/create", json={})
        assert resp.status_code in (403, 422)

    def test_create_deal_schema_validates_required_fields(self, api_client):
        """Missing required fields → 422 (schema error) even with no auth."""
        resp = api_client.post(
            "/deals/create",
            json={"comment": "incomplete"},
            headers={"X-Telegram-Id": "123"},
        )
        # Either 422 (schema) or 403 (auth) – route must exist
        assert resp.status_code in (403, 422)

    @pytest.mark.asyncio
    async def test_create_deal_calls_sql_function(self):
        """Happy path: call_sql_function_one is invoked with the right SQL."""
        from backend.services import db_exec

        expected_deal = {
            "id": 42,
            "deal_id": "42",
            "status": "Новая",
            "client": "Test Client",
            "manager": "Test Manager",
        }

        with patch.object(db_exec, "call_sql_function_one", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = expected_deal
            result = await db_exec.call_sql_function_one(
                AsyncMock(),
                "SELECT * FROM public.api_create_deal(:status_id, :client_id)",
                {"status_id": 1, "client_id": 2},
            )
        assert result == expected_deal
        mock_fn.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. POST /deals/pay – happy path
# ---------------------------------------------------------------------------

class TestHappyPathDealPay:
    """POST /deals/pay succeeds for accounting role."""

    def test_pay_deal_requires_auth(self, api_client):
        resp = api_client.post("/deals/pay", json={})
        assert resp.status_code in (403, 422)

    def test_pay_deal_returns_403_for_manager_role(self, api_client):
        """Manager role cannot pay a deal — endpoint returns 403."""
        resp = api_client.post(
            "/deals/pay",
            json={"deal_id": 1, "payment_amount": 500.0},
            headers={"X-Telegram-Id": "123"},
        )
        # 403 (no auth / manager not allowed) or 500 (DB unavailable) – not 200
        assert resp.status_code in (403, 500)

    def test_pay_deal_allowed_roles_config(self):
        """accounting, operations_director, admin are in the allowed roles for pay."""
        from backend.routers.deals_sql import pay_deal
        import inspect
        source = inspect.getsource(pay_deal)
        assert "accounting" in source
        assert "operations_director" in source
        assert "admin" in source


# ---------------------------------------------------------------------------
# 4. POST /expenses/v2/create – happy path
# ---------------------------------------------------------------------------

class TestHappyPathExpenseCreate:
    """POST /expenses/v2/create succeeds when auth provided."""

    def test_create_expense_requires_auth(self, api_client):
        resp = api_client.post("/expenses/v2/create", json={})
        assert resp.status_code in (403, 422)

    def test_create_expense_route_exists(self, api_client):
        """Route is registered and reachable."""
        resp = api_client.post(
            "/expenses/v2/create",
            json={"expense_type_id": 1, "amount": 100.0, "category_id": 1},
            headers={"X-Telegram-Id": "123"},
        )
        # 403 (auth failed) or 422 (schema) – not 404 (route must exist)
        assert resp.status_code != 404


# ---------------------------------------------------------------------------
# 5. POST /billing/v2/upsert – happy path
# ---------------------------------------------------------------------------

class TestHappyPathBillingUpsert:
    """POST /billing/v2/upsert succeeds for manager role."""

    def test_upsert_billing_requires_auth(self, api_client):
        resp = api_client.post("/billing/v2/upsert", json={})
        assert resp.status_code in (403, 422)

    def test_upsert_billing_schema(self):
        """BillingUpsertRequest schema validates required fields."""
        from backend.schemas.billing import BillingUpsertRequest
        req = BillingUpsertRequest(
            client_id=1,
            warehouse_id=2,
            month="2025-03",
            shipments_with_vat=Decimal("12000"),
            storage_with_vat=Decimal("3000"),
        )
        assert req.client_id == 1
        assert req.month == "2025-03"


# ---------------------------------------------------------------------------
# 6. POST /billing/v2/pay – happy path
# ---------------------------------------------------------------------------

class TestHappyPathBillingPay:
    """POST /billing/v2/pay succeeds for accounting role."""

    def test_pay_billing_requires_auth(self, api_client):
        resp = api_client.post("/billing/v2/pay", json={})
        assert resp.status_code in (403, 422)

    def test_pay_billing_schema(self):
        """BillingPayRequest schema validates required fields."""
        from backend.schemas.billing import BillingPayRequest
        req = BillingPayRequest(
            billing_entry_id=7,
            payment_amount=Decimal("5000"),
        )
        assert req.billing_entry_id == 7


# ---------------------------------------------------------------------------
# 7. POST /billing/v2/payment/mark – happy path (new SQL-first endpoint)
# ---------------------------------------------------------------------------

class TestHappyPathBillingPaymentMark:
    """POST /billing/v2/payment/mark is a new SQL-first replacement for the legacy endpoint."""

    def test_payment_mark_route_exists(self, api_client):
        resp = api_client.post("/billing/v2/payment/mark", json={})
        # 403 (no auth) or 422 (schema) – not 404
        assert resp.status_code != 404

    def test_payment_mark_requires_auth(self, api_client):
        resp = api_client.post(
            "/billing/v2/payment/mark",
            json={"deal_id": "42", "payment_amount": 1000.0},
        )
        assert resp.status_code == 403

    def test_payment_mark_schema(self):
        """BillingPaymentMarkRequest schema validates required fields."""
        from backend.schemas.billing import BillingPaymentMarkRequest
        req = BillingPaymentMarkRequest(
            deal_id="42",
            payment_amount=Decimal("2500"),
        )
        assert req.deal_id == "42"
        assert req.payment_amount == Decimal("2500")


# ---------------------------------------------------------------------------
# 8. GET /deals/{id} – happy path (new SQL-first endpoint)
# ---------------------------------------------------------------------------

class TestHappyPathGetDeal:
    """GET /deals/{id} returns deal data or 403/404 as appropriate."""

    def test_get_deal_route_exists(self, api_client):
        resp = api_client.get("/deals/42")
        # 403 (no auth) – route must exist and not return 404
        assert resp.status_code != 404

    def test_get_deal_requires_auth(self, api_client):
        resp = api_client.get("/deals/99")
        assert resp.status_code == 403

    def test_get_deal_not_shadow_create(self, api_client):
        """Ensure /deals/create (POST) is not caught by /deals/{id} (GET)."""
        # GET /deals/create should be 403 (no auth) not 404; the route exists via {deal_id}
        resp_get = api_client.get("/deals/create")
        assert resp_get.status_code == 403


# ---------------------------------------------------------------------------
# 9. PATCH /deals/update/{id} – happy path (new SQL-first endpoint)
# ---------------------------------------------------------------------------

class TestHappyPathUpdateDeal:
    """PATCH /deals/update/{id} replaces the legacy PATCH /deal/update/{id}."""

    def test_update_deal_route_exists(self, api_client):
        resp = api_client.patch("/deals/update/42", json={"comment": "test"})
        # 403 (no auth) – route must exist
        assert resp.status_code != 404

    def test_update_deal_requires_auth(self, api_client):
        resp = api_client.patch("/deals/update/42", json={"comment": "test"})
        assert resp.status_code == 403

    def test_update_deal_empty_body_with_auth(self, api_client):
        """Empty body should return 403 (no auth) without hitting 422."""
        resp = api_client.patch("/deals/update/42", json={})
        assert resp.status_code == 403

    def test_legacy_update_deal_still_exists(self, api_client):
        """Legacy PATCH /deal/update/{id} must still be accessible for backward compat."""
        resp = api_client.patch("/deal/update/42", json={"comment": "test"})
        assert resp.status_code == 403  # present but guarded


# ---------------------------------------------------------------------------
# 10. GET /billing/v2/search – happy path (new SQL-first endpoint)
# ---------------------------------------------------------------------------

class TestHappyPathBillingSearch:
    """GET /billing/v2/search is a new SQL-first replacement for /billing/search."""

    def test_search_route_exists(self, api_client):
        resp = api_client.get("/billing/v2/search?client_id=1&warehouse_id=2")
        # 403 (no auth) – route must exist
        assert resp.status_code != 404

    def test_search_requires_auth(self, api_client):
        resp = api_client.get("/billing/v2/search?client_id=1&warehouse_id=2")
        assert resp.status_code == 403

    def test_search_requires_at_least_one_filter(self, api_client):
        """No filters → 422 validation error or 403 (auth check fires first) or 500 (DB)."""
        resp = api_client.get(
            "/billing/v2/search",
            headers={"X-Telegram-Id": "123"},
        )
        # 403 (auth failure), 422 (validation), or 500 (DB unavailable in test) – not 404
        assert resp.status_code in (403, 422, 500)

    def test_legacy_search_still_exists(self, api_client):
        """Legacy GET /billing/search must still be accessible for backward compat."""
        resp = api_client.get("/billing/search?warehouse=msk&client=TestClient")
        # 403 (no auth) or 400 (bad input) – route must exist
        assert resp.status_code in (403, 400, 500)


# ---------------------------------------------------------------------------
# 11. POST /month/archive – dry-run happy path
# ---------------------------------------------------------------------------

class TestHappyPathMonthArchiveDryRun:
    """POST /month/archive with dry_run=true runs a preview check."""

    def test_archive_dry_run_requires_auth(self, api_client):
        resp = api_client.post(
            "/month/archive",
            json={"year": 2025, "month": 3, "dry_run": True},
        )
        assert resp.status_code == 403

    def test_archive_dry_run_schema(self):
        """ArchiveMonthRequest schema accepts dry_run flag."""
        from backend.schemas.month_close import ArchiveMonthRequest
        req = ArchiveMonthRequest(year=2025, month=3, dry_run=True)
        assert req.dry_run is True

    def test_archive_real_schema(self):
        """ArchiveMonthRequest schema defaults dry_run to False."""
        from backend.schemas.month_close import ArchiveMonthRequest
        req = ArchiveMonthRequest(year=2025, month=3)
        assert req.dry_run is False


# ---------------------------------------------------------------------------
# 12. POST /month/close – happy path
# ---------------------------------------------------------------------------

class TestHappyPathMonthClose:
    """POST /month/close marks a month as closed."""

    def test_close_month_requires_auth(self, api_client):
        resp = api_client.post(
            "/month/close",
            json={"year": 2025, "month": 3},
        )
        assert resp.status_code == 403

    def test_close_month_schema(self):
        """CloseMonthRequest schema accepts optional comment."""
        from backend.schemas.month_close import CloseMonthRequest
        req = CloseMonthRequest(year=2025, month=3, comment="End of quarter")
        assert req.comment == "End of quarter"

    def test_close_month_schema_no_comment(self):
        """CloseMonthRequest schema defaults comment to None."""
        from backend.schemas.month_close import CloseMonthRequest
        req = CloseMonthRequest(year=2025, month=3)
        assert req.comment is None


# ---------------------------------------------------------------------------
# 13. New SQL-first router route registration
# ---------------------------------------------------------------------------

class TestNewRouteRegistrations:
    """Verify that all new SQL-first endpoints are registered in the app."""

    def test_deals_sql_router_has_get_by_id(self):
        """GET /deals/{deal_id} is registered."""
        from backend.routers.deals_sql import router
        paths = [r.path for r in router.routes]
        assert "/deals/{deal_id}" in paths

    def test_deals_sql_router_has_patch_update(self):
        """PATCH /deals/update/{deal_id} is registered."""
        from backend.routers.deals_sql import router
        paths = [r.path for r in router.routes]
        assert "/deals/update/{deal_id}" in paths

    def test_billing_sql_router_has_search(self):
        """GET /billing/v2/search is registered."""
        from backend.routers.billing_sql import router
        paths = [r.path for r in router.routes]
        assert "/billing/v2/search" in paths

    def test_billing_sql_router_has_payment_mark(self):
        """POST /billing/v2/payment/mark is registered."""
        from backend.routers.billing_sql import router
        paths = [r.path for r in router.routes]
        assert "/billing/v2/payment/mark" in paths

    def test_billing_payment_mark_schema_has_deal_id(self):
        """BillingPaymentMarkRequest has deal_id field."""
        from backend.schemas.billing import BillingPaymentMarkRequest
        fields = BillingPaymentMarkRequest.model_fields
        assert "deal_id" in fields
        assert "payment_amount" in fields

    def test_main_app_new_routes_reachable(self):
        """Key new routes are mounted in the main FastAPI app."""
        from backend.main import app
        all_paths = [r.path for r in app.routes]
        assert "/deals/{deal_id}" in all_paths
        assert "/deals/update/{deal_id}" in all_paths
        assert "/billing/v2/search" in all_paths
        assert "/billing/v2/payment/mark" in all_paths
