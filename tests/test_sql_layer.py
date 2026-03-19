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
    PostgreSQL raises: "List argument must consist only of tuples or dictionaries"
    (when params was a plain list) or FK violation (when params were swapped).

    Root cause: params was built as a Python list and passed to
    call_sql_function_one, which forwarded it to exec_driver_sql.  asyncpg
    treats a list as an executemany batch (each element must be a tuple/dict),
    causing the 500 crash.

    Fix: params must be a plain dict with :name placeholders in the SQL so
    that call_sql_function_one uses text() with named bind parameters and
    asyncpg maps each value by name — order in the dict does not matter.
    """

    def test_sql_has_manager_id_before_charged_with_vat(self):
        """
        params dict in create_deal must use named :param placeholders and
        must place :manager_id before :charged_with_vat in the SQL string to
        match the SQL function signature.  Verified by inspecting source code.
        """
        import inspect
        from backend.routers.deals_sql import create_deal

        source = inspect.getsource(create_deal)

        # Params must use named :name style, not positional $N
        assert ":manager_id" in source, (
            "create_deal must use named :manager_id bind param, not positional $N"
        )
        assert "$5" not in source, (
            "create_deal must NOT use positional $5 — use named :manager_id instead"
        )

        # :manager_id must appear before :charged_with_vat in the SQL string
        manager_pos = source.find(":manager_id")
        charged_pos = source.find(":charged_with_vat")

        assert manager_pos != -1, ":manager_id not found in create_deal source"
        assert charged_pos != -1, ":charged_with_vat not found in create_deal source"
        assert manager_pos < charged_pos, (
            "BUG: :manager_id appears AFTER :charged_with_vat in the SQL — "
            "they will be passed in the wrong order to the SQL function."
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
        charged_with_vat=123 as a plain dict (not a list) so that
        call_sql_function_one uses text() with named bind parameters instead
        of exec_driver_sql (which would raise "List argument must consist only
        of tuples or dictionaries").

        This is the primary guard against the 500 crash caused by passing a
        plain Python list to call_sql_function_one.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = params  # must be a plain dict
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
        assert isinstance(params, dict), (
            f"params must be a plain dict (not list/tuple), got {type(params).__name__} — "
            "passing a list causes: 'List argument must consist only of tuples or dictionaries'"
        )
        assert len(params) == 19, f"Expected 19 named params, got {len(params)}"

        # Verify manager_id and charged_with_vat are correctly bound by name
        assert params["manager_id"] == 1, (
            f"BUG: params['manager_id'] should be 1 but got {params['manager_id']!r} "
            f"— manager_id and charged_with_vat may be swapped"
        )
        assert params["charged_with_vat"] == Decimal("123"), (
            f"BUG: params['charged_with_vat'] should be Decimal('123') but got "
            f"{params['charged_with_vat']!r}"
        )
        # Confirm SQL uses named placeholders, not positional
        sql = captured["sql"]
        assert ":manager_id" in sql, ":manager_id named placeholder missing from SQL"
        assert ":charged_with_vat" in sql, ":charged_with_vat named placeholder missing from SQL"
        assert "$5" not in sql, "$5 positional placeholder must NOT be in SQL (use :manager_id)"
        assert "$6" not in sql, "$6 positional placeholder must NOT be in SQL (use :charged_with_vat)"


# ---------------------------------------------------------------------------
# Regression: billing/payment SQL signature fixes
# All three pay/upsert SQL functions require p_updated_by_user_id as FIRST arg.
# ---------------------------------------------------------------------------

class TestBillingUpdateByUserIdParameterOrder:
    """
    Regression tests ensuring updated_by_user_id is the FIRST parameter in
    all billing/payment SQL function calls.

    The PostgreSQL functions:
      - public.api_upsert_billing_entry(p_updated_by_user_id, p_client_id, ...)
      - public.api_pay_billing_entry(p_updated_by_user_id, p_billing_entry_id, ...)
      - public.api_pay_deal(p_updated_by_user_id, p_deal_id, ...)
    all require p_updated_by_user_id as position 1.
    """

    def test_billing_upsert_sql_has_updated_by_user_id_before_client_id(self):
        """billing_sql.py upsert: :updated_by_user_id must precede :client_id."""
        import inspect
        from backend.routers.billing_sql import upsert_billing_entry

        source = inspect.getsource(upsert_billing_entry)

        uid_pos = source.find(":updated_by_user_id")
        client_pos = source.find(":client_id")

        assert uid_pos != -1, ":updated_by_user_id not found in upsert_billing_entry SQL"
        assert client_pos != -1, ":client_id not found in upsert_billing_entry SQL"
        assert uid_pos < client_pos, (
            "BUG: :updated_by_user_id must be BEFORE :client_id in "
            "api_upsert_billing_entry — PostgreSQL function requires it as p_1."
        )

    def test_billing_pay_sql_has_updated_by_user_id_before_billing_entry_id(self):
        """billing_sql.py pay: :updated_by_user_id must precede :billing_entry_id."""
        import inspect
        from backend.routers.billing_sql import pay_billing_entry

        source = inspect.getsource(pay_billing_entry)

        uid_pos = source.find(":updated_by_user_id")
        entry_pos = source.find(":billing_entry_id")

        assert uid_pos != -1, ":updated_by_user_id not found in pay_billing_entry SQL"
        assert entry_pos != -1, ":billing_entry_id not found in pay_billing_entry SQL"
        assert uid_pos < entry_pos, (
            "BUG: :updated_by_user_id must be BEFORE :billing_entry_id in "
            "api_pay_billing_entry — PostgreSQL function requires it as p_1."
        )

    def test_billing_payment_mark_sql_has_updated_by_user_id_before_deal_id(self):
        """billing_sql.py payment/mark: :updated_by_user_id must precede :deal_id."""
        import inspect
        from backend.routers.billing_sql import mark_deal_payment

        source = inspect.getsource(mark_deal_payment)

        uid_pos = source.find(":updated_by_user_id")
        deal_pos = source.find(":deal_id")

        assert uid_pos != -1, ":updated_by_user_id not found in mark_deal_payment SQL"
        assert deal_pos != -1, ":deal_id not found in mark_deal_payment SQL"
        assert uid_pos < deal_pos, (
            "BUG: :updated_by_user_id must be BEFORE :deal_id in "
            "api_pay_deal (billing payment/mark) — PostgreSQL function requires it as p_1."
        )

    def test_deals_pay_sql_has_updated_by_user_id_before_deal_id(self):
        """deals_sql.py pay: :updated_by_user_id must precede :deal_id."""
        import inspect
        from backend.routers.deals_sql import pay_deal

        source = inspect.getsource(pay_deal)

        uid_pos = source.find(":updated_by_user_id")
        deal_pos = source.find(":deal_id")

        assert uid_pos != -1, ":updated_by_user_id not found in pay_deal SQL"
        assert deal_pos != -1, ":deal_id not found in pay_deal SQL"
        assert uid_pos < deal_pos, (
            "BUG: :updated_by_user_id must be BEFORE :deal_id in "
            "api_pay_deal (deals pay) — PostgreSQL function requires it as p_1."
        )

    @pytest.mark.asyncio
    async def test_billing_upsert_endpoint_passes_updated_by_user_id_first(self):
        """
        End-to-end: POST /billing/v2/upsert must pass updated_by_user_id as the
        first named param and it must appear first in the SQL string.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return {"id": 1, "client_id": 5, "warehouse_id": 3, "month": "2024-01"}

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.billing_sql.call_sql_function_one",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.billing_sql._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(42, "accounting", "Test User"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/billing/v2/upsert",
                        json={
                            "client_id": 5,
                            "warehouse_id": 3,
                            "month": "2024-01",
                            "shipments_with_vat": 10000,
                        },
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function_one was never called"
        params = captured["params"]
        assert "updated_by_user_id" in params, "updated_by_user_id missing from params"
        assert params["updated_by_user_id"] == 42, (
            f"updated_by_user_id should be 42 (user_id from auth), got {params['updated_by_user_id']!r}"
        )
        sql = captured["sql"]
        assert ":updated_by_user_id" in sql
        assert sql.index(":updated_by_user_id") < sql.index(":client_id"), (
            "BUG: :updated_by_user_id must appear before :client_id in SQL"
        )

    @pytest.mark.asyncio
    async def test_billing_pay_endpoint_passes_updated_by_user_id_first(self):
        """
        End-to-end: POST /billing/v2/pay must pass updated_by_user_id as the
        first named param.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return {"id": 1, "billing_entry_id": 10, "payment_amount": 5000}

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.billing_sql.call_sql_function_one",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.billing_sql._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(7, "accounting", "Accountant"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/billing/v2/pay",
                        json={"billing_entry_id": 10, "payment_amount": 5000},
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function_one was never called"
        params = captured["params"]
        assert "updated_by_user_id" in params
        assert params["updated_by_user_id"] == 7
        sql = captured["sql"]
        assert sql.index(":updated_by_user_id") < sql.index(":billing_entry_id"), (
            "BUG: :updated_by_user_id must appear before :billing_entry_id in SQL"
        )

    @pytest.mark.asyncio
    async def test_payment_mark_endpoint_passes_updated_by_user_id_first(self):
        """
        End-to-end: POST /billing/v2/payment/mark must pass updated_by_user_id
        as the first named param to api_pay_deal.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return {"id": 99, "remaining_amount": 0}

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.billing_sql.call_sql_function_one",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.billing_sql._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(15, "accounting", "Accountant"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/billing/v2/payment/mark",
                        json={"deal_id": "99", "payment_amount": 3000},
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function_one was never called"
        params = captured["params"]
        assert "updated_by_user_id" in params
        assert params["updated_by_user_id"] == 15
        sql = captured["sql"]
        assert sql.index(":updated_by_user_id") < sql.index(":deal_id"), (
            "BUG: :updated_by_user_id must appear before :deal_id in SQL"
        )

    @pytest.mark.asyncio
    async def test_deals_pay_endpoint_passes_updated_by_user_id_first(self):
        """
        End-to-end: POST /deals/pay must pass updated_by_user_id as the first
        named param to api_pay_deal.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return {"id": 55, "remaining_amount": 1000}

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
                    return_value=(33, "accounting", "Accountant"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/deals/pay",
                        json={"deal_id": 55, "payment_amount": 2000},
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function_one was never called"
        params = captured["params"]
        assert "updated_by_user_id" in params
        assert params["updated_by_user_id"] == 33
        sql = captured["sql"]
        assert sql.index(":updated_by_user_id") < sql.index(":deal_id"), (
            "BUG: :updated_by_user_id must appear before :deal_id in SQL"
        )

    @pytest.mark.asyncio
    async def test_billing_upsert_browser_mode_passes_none_for_updated_by_user_id(self):
        """
        In browser mode (X-User-Role only, no Telegram ID), user_id is "" (str),
        so updated_by_user_id must be None — not a string, not a fake int.
        """
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["params"] = dict(params)
            return {"id": 1, "month": "2024-01"}

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.billing_sql.call_sql_function_one",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.billing_sql._resolve_user",
                    new_callable=AsyncMock,
                    # Browser mode: user_id is "" (empty string, not integer)
                    return_value=("", "accounting", ""),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/billing/v2/upsert",
                        json={"client_id": 5, "warehouse_id": 3, "month": "2024-01"},
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured
        assert captured["params"]["updated_by_user_id"] is None, (
            "In browser mode (user_id=''), updated_by_user_id must be None, "
            f"got {captured['params']['updated_by_user_id']!r}"
        )

    @pytest.mark.asyncio
    async def test_billing_upsert_returns_500_when_sql_returns_no_result(self):
        """If SQL function returns no result, endpoint should return HTTP 500."""
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        async def return_none(db, sql, params):
            return None

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.billing_sql.call_sql_function_one",
                new_callable=AsyncMock,
                side_effect=return_none,
            ):
                with patch(
                    "backend.routers.billing_sql._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(1, "accounting", "Accountant"),
                ):
                    client = TestClient(app, raise_server_exceptions=False)
                    resp = client.post(
                        "/billing/v2/upsert",
                        json={"client_id": 5, "warehouse_id": 3, "month": "2024-01"},
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 500
                    assert "no result" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_payment_mark_returns_404_when_sql_returns_no_result(self):
        """If api_pay_deal returns no result, endpoint should return HTTP 404."""
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        async def return_none(db, sql, params):
            return None

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.billing_sql.call_sql_function_one",
                new_callable=AsyncMock,
                side_effect=return_none,
            ):
                with patch(
                    "backend.routers.billing_sql._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(1, "accounting", "Accountant"),
                ):
                    client = TestClient(app, raise_server_exceptions=False)
                    resp = client.post(
                        "/billing/v2/payment/mark",
                        json={"deal_id": "999", "payment_amount": 1000},
                        headers={"X-User-Role": "accounting"},
                    )
                    assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Regression: month_close SQL signature (month_key, started_by_user_id, notes, dry_run)
# ---------------------------------------------------------------------------

class TestMonthCloseSqlSignature:
    @pytest.mark.asyncio
    async def test_archive_uses_month_key_and_started_by_user_id_and_notes(self):
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return []

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.month_close.call_sql_function",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.month_close._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(77, "admin", "Admin"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/month/archive",
                        json={"year": 2024, "month": 1, "comment": "archive note", "dry_run": True},
                        headers={"X-User-Role": "admin"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function was never called"
        sql = captured["sql"]
        params = captured["params"]
        assert "public.archive_month(:month_key, :started_by_user_id, :notes, :dry_run)" in sql
        assert params["month_key"] == "2024-01"
        assert params["started_by_user_id"] == 77
        assert params["notes"] == "archive note"
        assert params["dry_run"] is True
        assert "year" not in params
        assert "month" not in params

    @pytest.mark.asyncio
    async def test_close_uses_month_key_and_started_by_user_id_and_prefers_notes(self):
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["sql"] = sql
            captured["params"] = dict(params)
            return []

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.month_close.call_sql_function",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.month_close._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(88, "operations_director", "Ops Dir"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/month/close",
                        json={
                            "year": 2024,
                            "month": 12,
                            "comment": "legacy comment",
                            "notes": "new notes",
                            "dry_run": False,
                        },
                        headers={"X-User-Role": "operations_director"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured, "call_sql_function was never called"
        sql = captured["sql"]
        params = captured["params"]
        assert "public.close_month(:month_key, :started_by_user_id, :notes, :dry_run)" in sql
        assert params["month_key"] == "2024-12"
        assert params["started_by_user_id"] == 88
        assert params["notes"] == "new notes"
        assert params["dry_run"] is False
        assert "year" not in params
        assert "month" not in params

    @pytest.mark.asyncio
    async def test_close_maps_comment_to_notes_when_notes_absent(self):
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["params"] = dict(params)
            return []

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.month_close.call_sql_function",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.month_close._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(55, "admin", "Admin"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/month/close",
                        json={"year": 2023, "month": 2, "comment": "fallback comment"},
                        headers={"X-User-Role": "admin"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured["params"]["month_key"] == "2023-02"
        assert captured["params"]["notes"] == "fallback comment"
        assert captured["params"]["dry_run"] is False

    @pytest.mark.asyncio
    async def test_archive_passes_none_notes_when_comment_and_notes_absent(self):
        from fastapi.testclient import TestClient
        from app.database.database import get_db
        from backend.main import app

        captured: dict = {}

        async def capture_params(db, sql, params):
            captured["params"] = dict(params)
            return []

        async def override_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.routers.month_close.call_sql_function",
                new_callable=AsyncMock,
                side_effect=capture_params,
            ):
                with patch(
                    "backend.routers.month_close._resolve_user",
                    new_callable=AsyncMock,
                    return_value=(11, "admin", "Admin"),
                ):
                    client = TestClient(app, raise_server_exceptions=True)
                    resp = client.post(
                        "/month/archive",
                        json={"year": 2025, "month": 3},
                        headers={"X-User-Role": "admin"},
                    )
                    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert captured["params"]["month_key"] == "2025-03"
        assert captured["params"]["notes"] is None
        assert captured["params"]["dry_run"] is False
