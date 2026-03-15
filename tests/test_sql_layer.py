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
