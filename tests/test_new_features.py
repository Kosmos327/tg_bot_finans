"""
Tests for the new features:
  - permissions.py: new roles, password auth, role access checks
  - billing_service.py: total calculations
  - expenses_service.py: add/list
  - reports_service.py: CSV/XLSX serialisation
  - auth router: POST /auth/role-login
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("WEBAPP_URL", "http://localhost")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
os.environ.setdefault("GOOGLE_SHEETS_SPREADSHEET_ID", "test")


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------

class TestPermissions:
    def test_allowed_roles_includes_new_roles(self):
        from backend.services.permissions import ALLOWED_ROLES
        assert "admin" in ALLOWED_ROLES
        assert "accounting" in ALLOWED_ROLES

    def test_verify_role_password_correct(self):
        from backend.services.permissions import verify_role_password
        assert verify_role_password("manager", "1") is True
        assert verify_role_password("operations_director", "2") is True
        assert verify_role_password("accounting", "3") is True
        assert verify_role_password("admin", "12345") is True

    def test_verify_role_password_wrong(self):
        from backend.services.permissions import verify_role_password
        assert verify_role_password("manager", "99") is False
        assert verify_role_password("admin", "1") is False

    def test_verify_role_password_unknown_role(self):
        from backend.services.permissions import verify_role_password
        assert verify_role_password("unknown_role", "1") is False

    def test_check_role_returns_true(self):
        from backend.services.permissions import check_role, BILLING_EDIT_ROLES
        assert check_role("manager", BILLING_EDIT_ROLES) is True
        assert check_role("admin", BILLING_EDIT_ROLES) is True

    def test_check_role_returns_false(self):
        from backend.services.permissions import check_role, BILLING_EDIT_ROLES
        assert check_role("accounting", BILLING_EDIT_ROLES) is False
        assert check_role("no_access", BILLING_EDIT_ROLES) is False

    def test_admin_can_view_journal(self):
        from backend.services.permissions import check_role, JOURNAL_VIEW_ROLES
        assert check_role("admin", JOURNAL_VIEW_ROLES) is True

    def test_manager_cannot_view_journal(self):
        from backend.services.permissions import check_role, JOURNAL_VIEW_ROLES
        assert check_role("manager", JOURNAL_VIEW_ROLES) is False

    def test_all_roles_can_add_expenses(self):
        from backend.services.permissions import check_role, EXPENSE_ADD_ROLES
        assert check_role("manager", EXPENSE_ADD_ROLES) is True
        assert check_role("accounting", EXPENSE_ADD_ROLES) is True
        assert check_role("operations_director", EXPENSE_ADD_ROLES) is True
        assert check_role("admin", EXPENSE_ADD_ROLES) is True

    def test_report_roles(self):
        from backend.services.permissions import check_role, REPORT_DOWNLOAD_ROLES
        assert check_role("operations_director", REPORT_DOWNLOAD_ROLES) is True
        assert check_role("accounting", REPORT_DOWNLOAD_ROLES) is True
        assert check_role("admin", REPORT_DOWNLOAD_ROLES) is True
        assert check_role("manager", REPORT_DOWNLOAD_ROLES) is False

    def test_admin_editable_fields_include_all(self):
        from backend.services.permissions import ROLE_EDITABLE_FIELDS
        admin_fields = ROLE_EDITABLE_FIELDS.get("admin", frozenset())
        assert len(admin_fields) > 0

    def test_accounting_can_see_all_deals(self):
        from backend.services.permissions import can_see_all_deals
        assert can_see_all_deals("accounting") is True


# ---------------------------------------------------------------------------
# billing_service (unit tests with mocked sheets)
# ---------------------------------------------------------------------------

class TestBillingTotals:
    """Test the internal _calc_totals helper directly."""

    def test_calculates_totals_correctly(self):
        from backend.services.billing_service import _calc_totals
        row = {
            "p1_shipments_amount": "1000",
            "p1_storage_amount": "500",
            "p1_returns_amount": "200",
            "p1_extra_services": "100",
            "p1_penalties": "50",
            "p2_shipments_amount": "0",
            "p2_storage_amount": "0",
            "p2_returns_amount": "0",
            "p2_extra_services": "0",
            "p2_penalties": "0",
        }
        result = _calc_totals(row)
        # p1: 1000 + 500 + 200 + 100 = 1800
        assert result["p1_total_without_penalties"] == 1800.0
        # p1: 1800 - 50 = 1750
        assert result["p1_total_with_penalties"] == 1750.0
        # p2: all zeros
        assert result["p2_total_without_penalties"] == 0.0
        assert result["p2_total_with_penalties"] == 0.0

    def test_zero_penalties(self):
        from backend.services.billing_service import _calc_totals
        row = {
            "p1_shipments_amount": "500",
            "p1_storage_amount": "0",
            "p1_returns_amount": "0",
            "p1_extra_services": "0",
            "p1_penalties": "0",
            "p2_shipments_amount": "0",
            "p2_storage_amount": "0",
            "p2_returns_amount": "0",
            "p2_extra_services": "0",
            "p2_penalties": "0",
        }
        result = _calc_totals(row)
        assert result["p1_total_without_penalties"] == 500.0
        assert result["p1_total_with_penalties"] == 500.0

    def test_col_letter_helper(self):
        from backend.services.billing_service import _col_letter
        assert _col_letter(0) == "A"
        assert _col_letter(1) == "B"
        assert _col_letter(25) == "Z"
        assert _col_letter(26) == "AA"

    def test_resolve_sheet_name(self):
        from backend.services.billing_service import _resolve_sheet_name
        assert "msk" in _resolve_sheet_name("msk").lower()
        assert "nsk" in _resolve_sheet_name("nsk").lower()
        assert "ekb" in _resolve_sheet_name("ekb").lower()

    def test_resolve_sheet_name_unknown_raises(self):
        from backend.services.billing_service import _resolve_sheet_name
        with pytest.raises(ValueError, match="Unknown warehouse"):
            _resolve_sheet_name("xyz")


# ---------------------------------------------------------------------------
# expenses_service (unit tests)
# ---------------------------------------------------------------------------

class TestExpensesService:
    def test_valid_expense_types(self):
        from backend.services.expenses_service import VALID_EXPENSE_TYPES
        assert "variable" in VALID_EXPENSE_TYPES
        assert "production" in VALID_EXPENSE_TYPES
        assert "logistics" in VALID_EXPENSE_TYPES
        assert "returns" in VALID_EXPENSE_TYPES
        assert "extra" in VALID_EXPENSE_TYPES

    @patch("backend.services.expenses_service.get_worksheet")
    @patch("backend.services.expenses_service.append_journal_entry")
    def test_add_expense_appends_row(self, mock_journal, mock_get_ws):
        ws = MagicMock()
        ws.row_values.return_value = []  # empty → headers will be written
        ws.col_values.return_value = ["expense_id"]  # no existing rows
        mock_get_ws.return_value = ws

        from backend.services.expenses_service import add_expense
        result = add_expense(
            data={"expense_type": "variable", "amount": 1500.0},
            user="test_user",
            role="manager",
        )

        assert result["expense_type"] == "variable"
        assert result["amount"] == 1500.0
        assert result["expense_id"] == "1"
        ws.append_row.assert_called()

    @patch("backend.services.expenses_service.get_worksheet")
    @patch("backend.services.expenses_service.append_journal_entry")
    def test_add_expense_invalid_type_raises(self, mock_journal, mock_get_ws):
        from backend.services.expenses_service import add_expense
        with pytest.raises(ValueError, match="expense_type"):
            add_expense(
                data={"expense_type": "bad_type", "amount": 100.0},
            )


# ---------------------------------------------------------------------------
# reports_service (unit tests – no Sheets API)
# ---------------------------------------------------------------------------

class TestReportsService:
    def test_to_csv_empty(self):
        from backend.services.reports_service import _to_csv
        result = _to_csv([], [])
        assert isinstance(result, bytes)

    def test_to_csv_with_data(self):
        from backend.services.reports_service import _to_csv
        result = _to_csv(["a", "b"], [["1", "2"], ["3", "4"]])
        text = result.decode("utf-8-sig")
        assert "a" in text
        assert "1" in text

    def test_to_xlsx_with_data(self):
        from backend.services.reports_service import _to_xlsx
        result = _to_xlsx(["col1", "col2"], [["v1", "v2"]])
        assert isinstance(result, bytes)
        # XLSX files start with PK (zip)
        assert result[:2] == b"PK"

    def test_serialise_csv(self):
        from backend.services.reports_service import _serialise
        data = [{"name": "Test", "amount": "1000"}]
        result = _serialise(data, "csv")
        text = result.decode("utf-8-sig")
        assert "name" in text
        assert "Test" in text

    def test_serialise_empty_data(self):
        from backend.services.reports_service import _serialise
        result = _serialise([], "csv")
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# deals_service: new VAT / profitability calculations
# ---------------------------------------------------------------------------

class TestDealFinancials:
    """Test the _calculate_deal_financials helper directly."""

    def test_vat_breakdown_calculated(self):
        from backend.services.deals_service import _calculate_deal_financials
        payload = {"charged_with_vat": 120.0, "vat_rate": 0.20}
        result = _calculate_deal_financials(payload)
        assert result["amount_without_vat"] == 100.0
        assert result["vat_amount"] == 20.0

    def test_vat_breakdown_zero_rate_not_calculated(self):
        from backend.services.deals_service import _calculate_deal_financials
        payload = {"charged_with_vat": 1200.0, "vat_rate": 0.0}
        result = _calculate_deal_financials(payload)
        # vat_rate=0.0 is falsy → skip auto-calc (no VAT means nothing to break down)
        # amount_without_vat and vat_amount are not populated when vat_rate is zero/absent
        assert "amount_without_vat" not in result
        assert "vat_amount" not in result

    def test_marginal_income_calculated(self):
        from backend.services.deals_service import _calculate_deal_financials
        payload = {
            "charged_with_vat": 1200.0,
            "vat_rate": 0.20,
            "variable_expense_1_with_vat": 240.0,
            "variable_expense_2_with_vat": 120.0,
        }
        result = _calculate_deal_financials(payload)
        # amount_without_vat = 1200/1.2 = 1000
        assert result["amount_without_vat"] == 1000.0
        # ve1_without_vat = 240/1.2 = 200
        assert result["variable_expense_1_without_vat"] == 200.0
        # ve2_without_vat = 120/1.2 = 100
        assert result["variable_expense_2_without_vat"] == 100.0
        # marginal_income = 1000 - 200 - 100 = 700
        assert result["marginal_income"] == 700.0

    def test_gross_profit_calculated(self):
        from backend.services.deals_service import _calculate_deal_financials
        payload = {
            "charged_with_vat": 1200.0,
            "vat_rate": 0.20,
            "variable_expense_1_with_vat": 240.0,
            "variable_expense_2_with_vat": 0.0,
            "production_expense_with_vat": 120.0,
        }
        result = _calculate_deal_financials(payload)
        # marginal_income = 1000 - 200 - 0 = 800
        assert result["marginal_income"] == 800.0
        # production_without_vat = 120/1.2 = 100
        assert result["production_expense_without_vat"] == 100.0
        # gross_profit = 800 - 100 = 700
        assert result["gross_profit"] == 700.0

    def test_manager_bonus_amount_calculated(self):
        from backend.services.deals_service import _calculate_deal_financials
        payload = {
            "charged_with_vat": 1200.0,
            "vat_rate": 0.20,
            "variable_expense_1_with_vat": 0.0,
            "variable_expense_2_with_vat": 0.0,
            "production_expense_with_vat": 0.0,
            "manager_bonus_percent": 10.0,
        }
        result = _calculate_deal_financials(payload)
        # gross_profit = 1000 (all expenses zero)
        assert result["gross_profit"] == 1000.0
        # bonus = 1000 * 10 / 100 = 100
        assert result["manager_bonus_amount"] == 100.0

    def test_vat_breakdown_for_variable_expenses(self):
        from backend.services.deals_service import _calculate_deal_financials
        payload = {
            "charged_with_vat": 600.0,
            "vat_rate": 0.20,
            "variable_expense_1_with_vat": 60.0,
        }
        result = _calculate_deal_financials(payload)
        assert result["variable_expense_1_vat"] == 10.0
        assert result["variable_expense_1_without_vat"] == 50.0


# ---------------------------------------------------------------------------
# billing_service: new VAT-aware format calculations
# ---------------------------------------------------------------------------

class TestBillingTotalsV2:
    """Test the new _calc_billing_totals_v2 helper."""

    def test_basic_vat_breakdown(self):
        from backend.services.billing_service import _calc_billing_totals_v2
        row = {"shipments_with_vat": 120.0}
        result = _calc_billing_totals_v2(row)
        assert result["shipments_without_vat"] == 100.0
        assert result["shipments_vat"] == 20.0

    def test_total_without_vat_minus_penalties(self):
        from backend.services.billing_service import _calc_billing_totals_v2
        row = {
            "shipments_with_vat": 120.0,
            "storage_with_vat": 60.0,
            "returns_pickup_with_vat": 0.0,
            "additional_services_with_vat": 0.0,
            "penalties": 5.0,
        }
        result = _calc_billing_totals_v2(row)
        # shipments_without_vat = 100, storage_without_vat = 50
        # total_without_vat = 100 + 50 + 0 + 0 - 5 = 145
        assert result["total_without_vat"] == 145.0

    def test_total_vat_sum(self):
        from backend.services.billing_service import _calc_billing_totals_v2
        row = {
            "shipments_with_vat": 120.0,
            "storage_with_vat": 60.0,
            "returns_pickup_with_vat": 0.0,
            "additional_services_with_vat": 0.0,
            "penalties": 0.0,
        }
        result = _calc_billing_totals_v2(row)
        # shipments_vat = 20, storage_vat = 10
        assert result["total_vat"] == 30.0

    def test_total_with_vat_equals_sum(self):
        from backend.services.billing_service import _calc_billing_totals_v2
        row = {
            "shipments_with_vat": 120.0,
            "storage_with_vat": 0.0,
            "returns_pickup_with_vat": 0.0,
            "additional_services_with_vat": 0.0,
            "penalties": 0.0,
        }
        result = _calc_billing_totals_v2(row)
        # total_with_vat = total_without_vat + total_vat = 100 + 20 = 120
        assert result["total_with_vat"] == 120.0

    def test_format_detection_new_format(self):
        from backend.services.billing_service import _is_new_format
        assert _is_new_format({"shipments_with_vat": 0, "client": 0}) is True

    def test_format_detection_old_format(self):
        from backend.services.billing_service import _is_new_format
        assert _is_new_format({"client_name": 0, "p1_shipments_amount": 0}) is False


# ---------------------------------------------------------------------------
# expenses_service: new VAT calculations
# ---------------------------------------------------------------------------

class TestExpensesVATCalc:
    """Test _calculate_expense_vat helper."""

    def test_vat_calc_20_percent(self):
        from backend.services.expenses_service import _calculate_expense_vat
        amount_no_vat, vat_amount = _calculate_expense_vat(120.0, 0.20)
        assert amount_no_vat == 100.0
        assert vat_amount == 20.0

    def test_vat_calc_zero_rate(self):
        from backend.services.expenses_service import _calculate_expense_vat
        amount_no_vat, vat_amount = _calculate_expense_vat(100.0, 0.0)
        # zero rate → returns original amount, 0 vat
        assert amount_no_vat == 100.0
        assert vat_amount == 0.0

    @patch("backend.services.expenses_service.get_worksheet")
    @patch("backend.services.expenses_service.append_journal_entry")
    def test_add_expense_new_style_keys(self, mock_journal, mock_get_ws):
        ws = MagicMock()
        ws.row_values.return_value = []
        ws.col_values.return_value = ["expense_id"]
        ws.row_values.return_value = []
        mock_get_ws.return_value = ws

        from backend.services.expenses_service import add_expense
        result = add_expense(
            data={
                "category": "production",
                "amount_with_vat": 240.0,
                "vat_rate": 0.20,
                "deal_id": "DEAL-000001",
            },
            user="test_user",
            role="accounting",
        )

        assert result["category"] == "production"
        assert result["amount_with_vat"] == 240.0
        assert result["vat_rate"] == 0.20
        assert result["amount_without_vat"] == 200.0
        assert result["vat_amount"] == 40.0
        # backward compat fields
        assert result["expense_type"] == "production"
        assert result["amount"] == 240.0

    @patch("backend.services.expenses_service.get_worksheet")
    @patch("backend.services.expenses_service.append_journal_entry")
    def test_add_expense_legacy_keys_still_work(self, mock_journal, mock_get_ws):
        ws = MagicMock()
        ws.row_values.return_value = []
        ws.col_values.return_value = ["expense_id"]
        mock_get_ws.return_value = ws

        from backend.services.expenses_service import add_expense
        result = add_expense(
            data={"expense_type": "variable", "amount": 1500.0, "vat": 250.0},
        )

        assert result["expense_type"] == "variable"
        assert result["category"] == "variable"
        assert result["amount"] == 1500.0

    @patch("backend.services.expenses_service.get_worksheet")
    @patch("backend.services.expenses_service.append_journal_entry")
    def test_add_expense_invalid_category_raises(self, mock_journal, mock_get_ws):
        from backend.services.expenses_service import add_expense
        with pytest.raises(ValueError, match="category"):
            add_expense(data={"category": "invalid_category", "amount_with_vat": 100.0})


# ---------------------------------------------------------------------------
# permissions: new fields in editable sets
# ---------------------------------------------------------------------------

class TestPermissionsNewFields:
    def test_vat_rate_in_business_fields(self):
        from backend.services.permissions import _BUSINESS_FIELDS
        assert "vat_rate" in _BUSINESS_FIELDS

    def test_new_accounting_fields_present(self):
        from backend.services.permissions import _ACCOUNTING_FIELDS
        assert "vat_amount" in _ACCOUNTING_FIELDS
        assert "amount_without_vat" in _ACCOUNTING_FIELDS
        assert "variable_expense_1_with_vat" in _ACCOUNTING_FIELDS
        assert "production_expense_with_vat" in _ACCOUNTING_FIELDS
        assert "gross_profit" in _ACCOUNTING_FIELDS
        assert "marginal_income" in _ACCOUNTING_FIELDS

    def test_admin_can_edit_new_fields(self):
        from backend.services.permissions import get_editable_fields
        admin_fields = get_editable_fields("admin")
        assert "vat_rate" in admin_fields
        assert "gross_profit" in admin_fields
        assert "marginal_income" in admin_fields

    def test_manager_cannot_edit_accounting_new_fields(self):
        from backend.services.permissions import get_editable_fields
        manager_fields = get_editable_fields("manager")
        # manager can set vat_rate (business field)
        assert "vat_rate" in manager_fields
        # manager cannot set accounting-level fields
        assert "gross_profit" not in manager_fields
        assert "variable_expense_1_with_vat" not in manager_fields


# ---------------------------------------------------------------------------
# auth router: POST /auth/role-login
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from backend.main import app
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestRoleLogin:
    def test_valid_manager_login(self, client):
        resp = client.post("/auth/role-login", json={"role": "manager", "password": "1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["role"] == "manager"

    def test_valid_admin_login(self, client):
        resp = client.post("/auth/role-login", json={"role": "admin", "password": "12345"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_valid_operations_director_login(self, client):
        resp = client.post("/auth/role-login", json={"role": "operations_director", "password": "2"})
        assert resp.status_code == 200

    def test_valid_accounting_login(self, client):
        resp = client.post("/auth/role-login", json={"role": "accounting", "password": "3"})
        assert resp.status_code == 200

    def test_wrong_password(self, client):
        resp = client.post("/auth/role-login", json={"role": "manager", "password": "999"})
        assert resp.status_code == 401

    def test_unknown_role(self, client):
        resp = client.post("/auth/role-login", json={"role": "unknown", "password": "1"})
        assert resp.status_code == 400

    def test_response_includes_role_label(self, client):
        resp = client.post("/auth/role-login", json={"role": "accounting", "password": "3"})
        data = resp.json()
        assert "role_label" in data
        assert len(data["role_label"]) > 0
