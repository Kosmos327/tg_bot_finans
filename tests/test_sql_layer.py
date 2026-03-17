"""
Tests for SQL-based services and new router endpoints.

Tests:
  - db_exec.py: _row_to_dict, _serialise, _clean_row, _extract_sql_error_message
  - miniapp_auth_service: _upsert_app_user_sql fallback behavior
  - New router endpoints: deals_sql, expenses_sql, billing_sql, month_close
  - Settings: load_enriched_settings_pg function signature
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from datetime import date, datetime
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
# db_exec helpers
# ---------------------------------------------------------------------------

class TestDbExecHelpers:
    def test_row_to_dict_with_mapping(self):
        from backend.services.db_exec import _row_to_dict
        mock_row = MagicMock()
        mock_row._mapping = {"id": 1, "name": "test"}
        result = _row_to_dict(mock_row)
        assert result == {"id": 1, "name": "test"}

    def test_row_to_dict_fallback(self):
        from backend.services.db_exec import _row_to_dict
        # Test with a regular dict (which has no _mapping)
        result = _row_to_dict({"id": 2, "name": "fallback"})
        assert result == {"id": 2, "name": "fallback"}

    def test_serialise_decimal(self):
        from backend.services.db_exec import _serialise
        result = _serialise(Decimal("123.45"))
        assert isinstance(result, float)
        assert result == 123.45

    def test_serialise_date(self):
        from backend.services.db_exec import _serialise
        d = date(2024, 1, 15)
        result = _serialise(d)
        assert result == "2024-01-15"

    def test_serialise_datetime(self):
        from backend.services.db_exec import _serialise
        dt = datetime(2024, 6, 1, 12, 0, 0)
        result = _serialise(dt)
        assert "2024-06-01" in result

    def test_serialise_other(self):
        from backend.services.db_exec import _serialise
        assert _serialise("hello") == "hello"
        assert _serialise(42) == 42
        assert _serialise(None) is None

    def test_clean_row(self):
        from backend.services.db_exec import _clean_row
        row = {"amount": Decimal("100.00"), "date": date(2024, 1, 1), "name": "test"}
        result = _clean_row(row)
        assert result["amount"] == 100.0
        assert result["date"] == "2024-01-01"
        assert result["name"] == "test"

    def test_extract_sql_error_message_generic(self):
        from backend.services.db_exec import _extract_sql_error_message
        err = Exception("some error")
        result = _extract_sql_error_message(err)
        assert "some error" in result


# ---------------------------------------------------------------------------
# Schemas validation
# ---------------------------------------------------------------------------

class TestDealCreateSchema:
    def test_valid_payload(self):
        from backend.schemas.deals import DealCreateRequest
        req = DealCreateRequest(
            status_id=1,
            business_direction_id=2,
            client_id=3,
            manager_id=4,
            charged_with_vat=Decimal("100000.00"),
        )
        assert req.status_id == 1
        assert req.paid == Decimal("0")

    def test_with_all_fields(self):
        from backend.schemas.deals import DealCreateRequest
        req = DealCreateRequest(
            status_id=1,
            business_direction_id=1,
            client_id=1,
            manager_id=1,
            charged_with_vat=Decimal("50000"),
            vat_type_id=1,
            vat_rate=Decimal("20"),
            paid=Decimal("10000"),
            project_start_date=date(2024, 1, 1),
            project_end_date=date(2024, 3, 31),
            manager_bonus_percent=Decimal("5"),
            document_link="https://example.com/doc",
            comment="Test deal",
        )
        assert req.vat_rate == Decimal("20")


class TestDealPaySchema:
    def test_valid_payload(self):
        from backend.schemas.deals import DealPayRequest
        req = DealPayRequest(deal_id=1, payment_amount=Decimal("5000"))
        assert req.deal_id == 1
        assert req.payment_date is None

    def test_with_payment_date(self):
        from backend.schemas.deals import DealPayRequest
        req = DealPayRequest(
            deal_id=1,
            payment_amount=Decimal("5000"),
            payment_date=date(2024, 6, 15),
        )
        assert req.payment_date == date(2024, 6, 15)


class TestBillingSchemas:
    def test_upsert_request(self):
        from backend.schemas.billing import BillingUpsertRequest
        req = BillingUpsertRequest(
            client_id=1,
            warehouse_id=2,
            month="2024-01",
            shipments_with_vat=Decimal("50000"),
        )
        assert req.month == "2024-01"

    def test_pay_request(self):
        from backend.schemas.billing import BillingPayRequest
        req = BillingPayRequest(billing_entry_id=10, payment_amount=Decimal("25000"))
        assert req.billing_entry_id == 10


class TestMonthCloseSchemas:
    def test_archive_request(self):
        from backend.schemas.month_close import ArchiveMonthRequest
        req = ArchiveMonthRequest(year=2024, month=1, dry_run=True)
        assert req.dry_run is True

    def test_cleanup_request(self):
        from backend.schemas.month_close import CleanupMonthRequest
        req = CleanupMonthRequest(year=2024, month=6)
        assert req.year == 2024

    def test_close_request(self):
        from backend.schemas.month_close import CloseMonthRequest
        req = CloseMonthRequest(year=2024, month=12, comment="End of year")
        assert req.comment == "End of year"


# ---------------------------------------------------------------------------
# New router registrations
# ---------------------------------------------------------------------------

class TestRouterRegistrations:
    def test_deals_sql_router_has_expected_routes(self):
        from backend.routers.deals_sql import router
        paths = [r.path for r in router.routes]
        assert "/deals" in paths
        assert "/deals/create" in paths
        assert "/deals/pay" in paths

    def test_expenses_sql_router_has_expected_routes(self):
        from backend.routers.expenses_sql import router
        paths = [r.path for r in router.routes]
        assert "/expenses/v2" in paths
        assert "/expenses/v2/create" in paths

    def test_billing_sql_router_has_expected_routes(self):
        from backend.routers.billing_sql import router
        paths = [r.path for r in router.routes]
        assert "/billing/v2" in paths
        assert "/billing/v2/upsert" in paths
        assert "/billing/v2/pay" in paths

    def test_month_close_router_has_expected_routes(self):
        from backend.routers.month_close import router
        paths = [r.path for r in router.routes]
        assert "/month/archive" in paths
        assert "/month/cleanup" in paths
        assert "/month/close" in paths
        assert "/month/archive-batches" in paths
        assert "/month/archived-deals" in paths

    def test_main_app_includes_new_routers(self):
        from backend.main import app
        all_paths = [r.path for r in app.routes]
        # Check key new paths are registered
        assert "/deals" in all_paths
        assert "/deals/create" in all_paths
        assert "/month/archive" in all_paths
        assert "/dashboard/summary" in all_paths


# ---------------------------------------------------------------------------
# miniapp_auth_service: _upsert_app_user_sql fallback
# ---------------------------------------------------------------------------

class TestUpsertAppUserSql:
    @pytest.mark.asyncio
    async def test_falls_back_to_orm_when_sql_function_fails(self):
        """When upsert_app_user SQL function is not available, fallback to ORM."""
        from app.database.models import AppUser, Role
        from backend.services import miniapp_auth_service as svc

        # Mock role object
        role_obj = Role()
        role_obj.id = 1
        role_obj.code = "manager"
        role_obj.name = "Менеджер"

        # Mock app user
        app_user = AppUser()
        app_user.id = 42
        app_user.telegram_id = 12345
        app_user.full_name = "Test"
        app_user.username = None
        app_user.role_id = 1
        app_user.is_active = True

        db = AsyncMock()
        db.flush = AsyncMock()

        async def fake_execute(stmt, params=None):
            result = MagicMock()
            stmt_str = str(stmt.text) if hasattr(stmt, 'text') else str(stmt)
            if "upsert_app_user" in stmt_str:
                # Simulate SQL function not available
                from sqlalchemy.exc import DBAPIError
                raise Exception("SQL function not found")
            elif "roles" in str(stmt_str):
                result.scalar_one_or_none.return_value = role_obj
            elif "app_users" in str(stmt_str):
                result.scalar_one_or_none.return_value = None  # new user
            else:
                result.scalar_one_or_none.return_value = None
            return result

        async def fake_refresh(obj):
            pass

        db.execute = fake_execute
        db.add = MagicMock(side_effect=lambda o: setattr(o, "id", 42))
        db.refresh = fake_refresh

        # Should not raise; should fall back to ORM
        user = await svc._upsert_app_user_sql(
            db, telegram_id=12345, full_name="Test", username=None, role_code="manager"
        )
        # Should have tried to create user via ORM (add was called)
        assert db.add.called


# ---------------------------------------------------------------------------
# Regression: create_deal parameter-order bug
# Bug: charged_with_vat=123 was landing in p_manager_id because the SQL call
# had the positional params in the wrong order.
# Fix: named SQLAlchemy bind params (:manager_id, :charged_with_vat) in the
# correct order so asyncpg's positional $N mapping is unambiguous.
# ---------------------------------------------------------------------------

class TestDealCreateParameterOrder:
    """
    Regression tests for the parameter-order bug in POST /deals/create.

    Symptoms: frontend sends manager_id=1 and charged_with_vat=123, but
    PostgreSQL raises: Key (manager_id)=(123) is not present in table "managers"

    Root cause: asyncpg converts named SQLAlchemy bind params (:name) to
    positional $N placeholders in the ORDER they first appear in the SQL string.
    If :charged_with_vat appeared before :manager_id, the value 123 would be
    passed as $4 → p_manager_id, triggering the FK violation.
    """

    def test_sql_has_manager_id_before_charged_with_vat(self):
        """
        The SQL template in create_deal must have :manager_id before
        :charged_with_vat so asyncpg's positional $4/:manager_id maps
        correctly to p_manager_id in the SQL function.
        """
        import inspect
        from backend.routers.deals_sql import create_deal

        source = inspect.getsource(create_deal)

        manager_pos = source.find(":manager_id")
        charged_pos = source.find(":charged_with_vat")

        assert manager_pos != -1, ":manager_id not found in create_deal source"
        assert charged_pos != -1, ":charged_with_vat not found in create_deal source"
        assert manager_pos < charged_pos, (
            "BUG: :manager_id appears AFTER :charged_with_vat in the SQL — "
            "asyncpg will swap their $N positions and charged_with_vat will "
            "be passed as p_manager_id, causing FK violations."
        )

    def test_model_dump_does_not_swap_manager_id_and_charged_with_vat(self):
        """
        model_dump() must return manager_id=1 and charged_with_vat=123 with
        distinct, unswapped values so that named bind param lookup is correct.
        """
        from backend.schemas.deals import DealCreateRequest

        req = DealCreateRequest(
            status_id=1,
            business_direction_id=2,
            client_id=3,
            manager_id=1,
            charged_with_vat=Decimal("123"),
        )
        params = req.model_dump()

        assert params["manager_id"] == 1, (
            f"manager_id should be 1, got {params['manager_id']!r} — "
            "values may have been swapped during model construction"
        )
        assert params["charged_with_vat"] == Decimal("123"), (
            f"charged_with_vat should be Decimal('123'), got {params['charged_with_vat']!r}"
        )
        assert params["manager_id"] != params["charged_with_vat"], (
            "manager_id and charged_with_vat have the same value — cannot detect a swap"
        )

    @pytest.mark.asyncio
    async def test_create_deal_endpoint_binds_manager_id_and_charged_with_vat_correctly(self):
        """
        End-to-end regression: POST /deals/create must pass manager_id=1 and
        charged_with_vat=123 to call_sql_function_one without swapping them.

        This is the primary guard against the original FK bug where
        charged_with_vat=123 was sent as p_manager_id to the SQL function.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return {"id": 42, "deal_id": "DEAL-000042", "status": "Новая"}

        # Provide a no-op async DB session so get_db doesn't attempt a real connection
        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                    "backend.routers.deals_sql.call_sql_function_one",
                    new_callable=AsyncMock,
                    side_effect=capture_params,
                ):
                with patch(
                    "backend.routers.deals_sql._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(1, "admin", "Test Admin"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/deals/create",
                        json={
                            "status_id": 1,
                            "business_direction_id": 2,
                            "client_id": 3,
                            "manager_id": 1,
                            "charged_with_vat": 123,
                        },
                        headers={"X-User-Role": "admin"},
                    )
                    assert resp.status_code == 200, (
                        f"Expected 200, got {resp.status_code}: {resp.text}"
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function_one was never called — route did not reach the SQL layer"

        params = captured["params"]
        assert params["manager_id"] == 1, (
            f"BUG: manager_id should be 1 but got {params.get('manager_id')!r} "
            f"(charged_with_vat={params.get('charged_with_vat')!r}) — "
            "manager_id and charged_with_vat are swapped in the SQL call"
        )
        assert params["charged_with_vat"] == Decimal("123"), (
            f"BUG: charged_with_vat should be Decimal('123') but got "
            f"{params.get('charged_with_vat')!r}"
        )
        # Confirm SQL contains named params in the right order
        sql = captured["sql"]
        assert ":manager_id" in sql, ":manager_id bind param missing from SQL"
        assert ":charged_with_vat" in sql, ":charged_with_vat bind param missing from SQL"
        assert sql.index(":manager_id") < sql.index(":charged_with_vat"), (
            "BUG: :manager_id appears after :charged_with_vat in the captured SQL — "
            "parameter order mismatch will cause FK violation at runtime"
        )
