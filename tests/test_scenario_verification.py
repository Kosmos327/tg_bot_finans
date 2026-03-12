"""
Scenario-based verification tests for the backend services.

Covers the 12 QA scenarios from the issue:
  1.  Manager creates a deal
  2.  Manager edits own deal
  3.  Manager tries to edit forbidden accounting fields
  4.  Accountant updates payment fields
  5.  Accountant views all deals
  6.  Operations director opens analytics / dashboard
  7.  Head of sales views manager performance
  8.  Unknown user opens app
  9.  Inactive user opens app
  10. Google Sheets settings block is partially empty
  11. Deal ID column contains malformed values
  12. Journal sheet exists but has missing headers
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Paths for imports that do not use the "backend." prefix
# ---------------------------------------------------------------------------

import sys
import os

# Insert repo root so we can import backend.* packages directly
_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_ws(headers: list[str], rows: list[list[str]] | None = None) -> MagicMock:
    """Return a mock gspread Worksheet whose first row contains *headers*."""
    ws = MagicMock()
    ws.title = "TestSheet"
    header_row = headers
    data_rows = rows or []
    ws.row_values.return_value = header_row
    ws.get_all_values.return_value = [header_row] + data_rows
    return ws


# ---------------------------------------------------------------------------
# Scenario 1 & 2: Manager creates / edits own deal
# ---------------------------------------------------------------------------


class TestScenario1_ManagerCreatesDeal:
    """Scenario 1 – manager creates a deal: accounting fields must be zeroed out."""

    def test_accounting_fields_are_stripped_for_manager(self):
        """
        A manager submitting accounting fields (paid, variable_expense_1 …)
        must NOT have those values persisted; they must be reset to defaults.
        """
        from backend.services.permissions import filter_update_payload, _ACCOUNTING_FIELDS

        # Simulate a manager sending a full payload including forbidden fields
        raw_payload = {
            "status": "В работе",
            "business_direction": "Разработка",
            "client": "ООО Тест",
            "manager": "Другой Менеджер",  # should be replaced by own name
            "charged_with_vat": 100_000,
            "vat_type": "С НДС",
            "project_start_date": "2025-01-01",
            "project_end_date": "2025-06-30",
            # Forbidden for managers:
            "paid": 50_000,
            "variable_expense_1": 10_000,
            "manager_bonus_percent": 5,
        }

        permitted = filter_update_payload("manager", raw_payload)

        # Accounting fields must be absent after filtering
        for field in _ACCOUNTING_FIELDS:
            assert field not in permitted, (
                f"Field '{field}' must be stripped for manager role but was kept"
            )

        # Business fields must be preserved
        assert "status" in permitted
        assert "client" in permitted
        assert "charged_with_vat" in permitted

    def test_manager_field_is_overridden_with_own_name(self):
        """
        When a manager creates a deal, the 'manager' field must be set to
        their own full_name, even if they supplied a different name.
        """
        from backend.services.deals_service import create_deal
        from backend.services.sheets_service import SHEET_DEALS, SHEET_JOURNAL

        deal_data = {
            "status": "В работе",
            "business_direction": "Разработка",
            "client": "ООО Тест",
            "manager": "Другой Менеджер",  # impersonation attempt
            "charged_with_vat": 100_000,
            "vat_type": "С НДС",
            "project_start_date": "2025-01-01",
            "project_end_date": "2025-06-30",
        }

        headers = [
            "ID сделки",
            "Статус сделки",
            "Направление бизнеса",
            "Клиент",
            "Менеджер",
            "Начислено с НДС",
            "Наличие НДС",
            "Оплачено",
            "Дата начала проекта",
            "Дата окончания проекта",
            "Дата выставления акта",
            "Переменный расход 1",
            "Переменный расход 2",
            "Бонус менеджера %",
            "Бонус менеджера выплачено",
            "Общепроизводственный расход",
            "Источник",
            "Документ/ссылка",
            "Комментарий",
        ]

        deals_ws = _make_ws(headers, [])
        journal_ws = _make_ws(list("timestamp telegram_user_id full_name".split()))
        journal_ws.row_values.return_value = []  # empty journal sheet

        with patch(
            "backend.services.deals_service.get_worksheet",
            side_effect=lambda name: deals_ws if "сделок" in name else journal_ws,
        ), patch(
            "backend.services.deals_service.get_header_map",
            return_value={h: i for i, h in enumerate(headers)},
        ), patch(
            "backend.services.journal_service.get_worksheet",
            return_value=journal_ws,
        ):
            deal_id = create_deal(
                deal_data=deal_data,
                telegram_user_id="123",
                user_role="manager",
                full_name="Иван Петров",
            )

        assert deal_id.startswith("DEAL-")
        # The appended row must contain the manager's OWN name (index 4)
        appended_row = deals_ws.append_row.call_args[0][0]
        manager_name_in_row = appended_row[4]  # "Менеджер" is at index 4
        assert manager_name_in_row == "Иван Петров", (
            f"Manager field should be overridden with own name, got: {manager_name_in_row}"
        )


# ---------------------------------------------------------------------------
# Scenario 3: Manager tries to edit forbidden accounting fields
# ---------------------------------------------------------------------------


class TestScenario3_ManagerForbiddenFields:
    """
    Scenario 3 – manager attempts to set accounting fields during update.
    Forbidden fields must be rejected, not silently accepted, and a 422
    must be raised when no permitted fields remain.
    """

    def test_update_raises_valueerror_when_all_fields_forbidden(self):
        """
        If a manager sends ONLY accounting fields (all forbidden), the service
        must raise ValueError rather than returning False (which the router
        would incorrectly map to HTTP 404).
        """
        from backend.services.deals_service import update_deal

        update_data = {
            "paid": 50_000.0,
            "variable_expense_1": 10_000.0,
            "manager_bonus_percent": 5.0,
        }

        # No sheet calls needed – ValueError should fire before any I/O
        with pytest.raises(ValueError, match="No fields in the request are editable"):
            update_deal(
                deal_id="DEAL-000001",
                update_data=update_data,
                telegram_user_id="123",
                user_role="manager",
                full_name="Иван Петров",
            )

    def test_partial_forbidden_fields_are_silently_dropped(self):
        """
        If a manager sends a mix of allowed and forbidden fields, the forbidden
        ones are stripped and the update proceeds with only the allowed fields.
        """
        from backend.services.deals_service import update_deal
        from backend.services.sheets_service import SHEET_DEALS, SHEET_JOURNAL

        headers = [
            "ID сделки", "Статус сделки", "Направление бизнеса", "Клиент",
            "Менеджер", "Начислено с НДС", "Наличие НДС", "Оплачено",
            "Дата начала проекта", "Дата окончания проекта", "Дата выставления акта",
            "Переменный расход 1", "Переменный расход 2", "Бонус менеджера %",
            "Бонус менеджера выплачено", "Общепроизводственный расход",
            "Источник", "Документ/ссылка", "Комментарий",
        ]
        header_map = {h: i for i, h in enumerate(headers)}

        existing_row = ["DEAL-000001", "В работе", "Разработка", "ООО Тест",
                        "Иван Петров", "100000", "С НДС", "0",
                        "2025-01-01", "2025-06-30", "", "0", "0", "0", "0", "0",
                        "", "", ""]

        deals_ws = _make_ws(headers, [existing_row])
        journal_ws = _make_ws([], [])
        journal_ws.row_values.return_value = []

        update_data = {
            "status": "Завершена",       # ALLOWED for manager
            "paid": 50_000.0,           # FORBIDDEN for manager
        }

        with patch(
            "backend.services.deals_service.get_worksheet",
            side_effect=lambda name: deals_ws if "сделок" in name else journal_ws,
        ), patch(
            "backend.services.deals_service.get_header_map",
            return_value=header_map,
        ), patch(
            "backend.services.journal_service.get_worksheet",
            return_value=journal_ws,
        ):
            result = update_deal(
                deal_id="DEAL-000001",
                update_data=update_data,
                telegram_user_id="123",
                user_role="manager",
                full_name="Иван Петров",
            )

        assert result is True
        # ws.update() was called – the allowed field was written
        deals_ws.update.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 4: Accountant updates payment fields
# ---------------------------------------------------------------------------


class TestScenario4_AccountantUpdatesPayment:
    """Scenario 4 – accountant may update accounting fields, not business fields."""

    def test_accountant_can_set_paid(self):
        """Accountant is permitted to write 'paid' and other accounting fields."""
        from backend.services.permissions import filter_update_payload, _ACCOUNTING_FIELDS

        payload = {
            "paid": 75_000.0,
            "act_date": "2025-03-01",
            "manager_bonus_percent": 10.0,
            # Forbidden for accountant:
            "status": "Завершена",
            "client": "ООО Другой",
        }

        result = filter_update_payload("accountant", payload)

        for field in _ACCOUNTING_FIELDS:
            if field in payload:
                assert field in result, f"Accountant must be allowed to set '{field}'"

        assert "status" not in result
        assert "client" not in result

    def test_accountant_cannot_set_business_fields(self):
        """Accountant must not be able to change business-side fields."""
        from backend.services.permissions import filter_update_payload, _BUSINESS_FIELDS

        payload = {f: "value" for f in _BUSINESS_FIELDS}
        result = filter_update_payload("accountant", payload)

        # Only 'comment' is shared; all pure business fields must be stripped
        business_only = _BUSINESS_FIELDS - {"comment"}
        for field in business_only:
            assert field not in result, (
                f"Accountant must NOT be allowed to set business field '{field}'"
            )


# ---------------------------------------------------------------------------
# Scenario 5: Accountant views all deals
# ---------------------------------------------------------------------------


class TestScenario5_AccountantViewsAllDeals:
    """Scenario 5 – accountant must have 'all' visibility scope."""

    def test_accountant_can_see_all_deals(self):
        from backend.services.permissions import can_see_all_deals

        assert can_see_all_deals("accountant") is True

    def test_manager_cannot_see_all_deals(self):
        from backend.services.permissions import can_see_all_deals

        assert can_see_all_deals("manager") is False


# ---------------------------------------------------------------------------
# Scenario 6 & 7: Operations director / Head of sales can see all
# ---------------------------------------------------------------------------


class TestScenario6And7_DirectorAndSalesHead:
    """Scenarios 6 & 7 – directors/head_of_sales can access all data."""

    def test_operations_director_can_see_all_deals(self):
        from backend.services.permissions import can_see_all_deals

        assert can_see_all_deals("operations_director") is True

    def test_head_of_sales_can_see_all_deals(self):
        from backend.services.permissions import can_see_all_deals

        assert can_see_all_deals("head_of_sales") is True

    def test_operations_director_can_edit_all_fields(self):
        """Operations director must be able to edit both business and accounting fields."""
        from backend.services.permissions import get_editable_fields, _BUSINESS_FIELDS, _ACCOUNTING_FIELDS

        editable = get_editable_fields("operations_director")
        for field in _BUSINESS_FIELDS | _ACCOUNTING_FIELDS:
            assert field in editable, (
                f"operations_director must be able to edit '{field}'"
            )

    def test_head_of_sales_can_edit_all_fields(self):
        """Head of sales must be able to edit both business and accounting fields."""
        from backend.services.permissions import get_editable_fields, _BUSINESS_FIELDS, _ACCOUNTING_FIELDS

        editable = get_editable_fields("head_of_sales")
        for field in _BUSINESS_FIELDS | _ACCOUNTING_FIELDS:
            assert field in editable, (
                f"head_of_sales must be able to edit '{field}'"
            )


# ---------------------------------------------------------------------------
# Scenario 8: Unknown user opens app
# ---------------------------------------------------------------------------


class TestScenario8_UnknownUser:
    """Scenario 8 – user not in the roles table gets no_access."""

    def test_unknown_user_gets_no_access_role(self):
        from backend.services.permissions import NO_ACCESS_ROLE
        from backend.services.settings_service import get_user_role

        with patch(
            "backend.services.settings_service.load_roles_mapping",
            return_value=[],  # empty table
        ):
            role = get_user_role("999999999")

        assert role == NO_ACCESS_ROLE

    def test_no_access_role_has_no_editable_fields(self):
        from backend.services.permissions import get_editable_fields, NO_ACCESS_ROLE

        assert get_editable_fields(NO_ACCESS_ROLE) == set()

    def test_no_access_role_cannot_see_all_deals(self):
        from backend.services.permissions import can_see_all_deals, NO_ACCESS_ROLE

        assert can_see_all_deals(NO_ACCESS_ROLE) is False


# ---------------------------------------------------------------------------
# Scenario 9: Inactive user opens app
# ---------------------------------------------------------------------------


class TestScenario9_InactiveUser:
    """Scenario 9 – known user who is marked inactive gets no_access."""

    def test_inactive_user_gets_no_access_role(self):
        from backend.services.permissions import NO_ACCESS_ROLE
        from backend.services.settings_service import get_user_role

        inactive_entry = {
            "telegram_user_id": "111111",
            "full_name": "Иван Иванов",
            "role": "manager",
            "active": False,  # marked inactive
        }

        with patch(
            "backend.services.settings_service.load_roles_mapping",
            return_value=[inactive_entry],
        ):
            role = get_user_role("111111")

        assert role == NO_ACCESS_ROLE

    def test_inactive_user_is_not_active(self):
        from backend.services.settings_service import is_user_active

        inactive_entry = {
            "telegram_user_id": "111111",
            "full_name": "Иван Иванов",
            "role": "manager",
            "active": False,
        }

        with patch(
            "backend.services.settings_service.load_roles_mapping",
            return_value=[inactive_entry],
        ):
            assert is_user_active("111111") is False


# ---------------------------------------------------------------------------
# Scenario 10: Google Sheets settings block is partially empty
# ---------------------------------------------------------------------------


class TestScenario10_PartiallyEmptySettings:
    """Scenario 10 – missing settings sections fall back to hardcoded defaults."""

    def test_empty_statuses_section_uses_defaults(self):
        from backend.services.settings_service import _DEFAULTS, parse_settings_sheet

        # Sheet with no statuses section
        rows: list[list[str]] = [
            ["[Клиенты]"],
            ["ООО Тест"],
        ]
        parsed = parse_settings_sheet(rows)
        # statuses should be empty (caller applies defaults separately)
        assert parsed["statuses"] == []

    def test_load_section_returns_defaults_when_empty(self):
        from backend.services.settings_service import _DEFAULTS, _load_section

        with patch(
            "backend.services.settings_service.get_worksheet"
        ) as mock_get_ws:
            mock_ws = MagicMock()
            mock_ws.get_all_values.return_value = []  # completely empty sheet
            mock_get_ws.return_value = mock_ws

            statuses = _load_section("statuses")

        assert statuses == _DEFAULTS["statuses"]

    def test_roles_section_missing_returns_empty_list(self):
        from backend.services.settings_service import parse_settings_sheet

        rows: list[list[str]] = [
            ["[Статусы сделок]"],
            ["В работе"],
        ]
        parsed = parse_settings_sheet(rows)
        assert parsed["roles_mapping"] == []


# ---------------------------------------------------------------------------
# Scenario 11: Deal ID column contains malformed values
# ---------------------------------------------------------------------------


class TestScenario11_MalformedDealIds:
    """
    Scenario 11 – rows with malformed deal IDs must not crash the service
    and must not be silently included as valid deals.
    """

    def test_parse_deal_id_number_rejects_malformed(self):
        from backend.services.deals_service import parse_deal_id_number

        assert parse_deal_id_number("DEAL-000001") == 1
        assert parse_deal_id_number("DEAL-000042") == 42
        # Malformed values:
        assert parse_deal_id_number("123") is None
        assert parse_deal_id_number("DEAL-") is None
        assert parse_deal_id_number("DEAL-abc") is None
        assert parse_deal_id_number("") is None
        assert parse_deal_id_number(None) is None  # type: ignore[arg-type]
        assert parse_deal_id_number("deal-000001") is None  # wrong case

    def test_generate_next_deal_id_skips_malformed(self):
        """Malformed IDs are silently ignored; next ID is based on valid ones only."""
        from backend.services.deals_service import generate_next_deal_id

        existing = ["DEAL-000001", "DEAL-000003", "INVALID", "123", ""]
        result = generate_next_deal_id(existing)
        assert result == "DEAL-000004"

    def test_generate_next_deal_id_with_all_malformed(self):
        """When ALL IDs are malformed, generation starts from DEAL-000001."""
        from backend.services.deals_service import generate_next_deal_id

        existing = ["123", "INVALID", "abc", ""]
        result = generate_next_deal_id(existing)
        assert result == "DEAL-000001"

    def test_read_all_deal_rows_skips_rows_with_empty_id(self):
        """Rows with empty deal_id column must be skipped."""
        from backend.services.deals_service import _read_all_deal_rows

        headers = [
            "ID сделки", "Статус сделки", "Направление бизнеса", "Клиент",
            "Менеджер", "Начислено с НДС", "Наличие НДС", "Оплачено",
            "Дата начала проекта", "Дата окончания проекта", "Дата выставления акта",
            "Переменный расход 1", "Переменный расход 2", "Бонус менеджера %",
            "Бонус менеджера выплачено", "Общепроизводственный расход",
            "Источник", "Документ/ссылка", "Комментарий",
        ]

        rows = [
            ["DEAL-000001"] + ["x"] * (len(headers) - 1),
            [""] + ["y"] * (len(headers) - 1),            # empty id – must be skipped
            ["DEAL-000002"] + ["z"] * (len(headers) - 1),
        ]

        mock_ws = _make_ws(headers, rows)

        with patch("backend.services.deals_service.get_worksheet", return_value=mock_ws), \
             patch("backend.services.deals_service.get_header_map",
                   return_value={h: i for i, h in enumerate(headers)}):
            deals = _read_all_deal_rows()

        assert len(deals) == 2
        ids = [d["deal_id"] for d in deals]
        assert "DEAL-000001" in ids
        assert "DEAL-000002" in ids


# ---------------------------------------------------------------------------
# Scenario 12: Journal sheet exists but has missing headers
# ---------------------------------------------------------------------------


class TestScenario12_JournalMissingHeaders:
    """
    Scenario 12 – journal sheet exists but some expected headers are absent.
    The service must log a warning rather than silently writing to wrong columns.
    """

    def test_ensure_headers_writes_header_when_sheet_is_empty(self):
        from backend.services.journal_service import _ensure_headers, JOURNAL_HEADERS

        ws = MagicMock()
        ws.row_values.return_value = []  # completely empty sheet

        _ensure_headers(ws)

        ws.append_row.assert_called_once_with(
            JOURNAL_HEADERS, value_input_option="USER_ENTERED"
        )

    def test_ensure_headers_does_not_overwrite_valid_headers(self):
        """If correct headers already exist, no additional row is written."""
        from backend.services.journal_service import _ensure_headers, JOURNAL_HEADERS

        ws = MagicMock()
        ws.row_values.return_value = JOURNAL_HEADERS[:]  # all headers present

        _ensure_headers(ws)

        ws.append_row.assert_not_called()

    def test_ensure_headers_logs_warning_for_partial_headers(self, caplog):
        """Missing headers in an existing sheet must produce a warning."""
        from backend.services.journal_service import _ensure_headers

        ws = MagicMock()
        # Sheet has some, but not all, expected headers
        ws.row_values.return_value = ["timestamp", "action"]  # missing the rest

        with caplog.at_level(logging.WARNING, logger="backend.services.journal_service"):
            _ensure_headers(ws)

        assert any("missing" in record.message.lower() for record in caplog.records), (
            "A WARNING about missing journal headers should have been logged"
        )

    def test_ensure_headers_logs_warning_for_completely_wrong_headers(self, caplog):
        """Completely unrecognised headers must trigger a warning."""
        from backend.services.journal_service import _ensure_headers

        ws = MagicMock()
        ws.row_values.return_value = ["col_a", "col_b", "col_c"]  # wrong headers

        with caplog.at_level(logging.WARNING, logger="backend.services.journal_service"):
            _ensure_headers(ws)

        assert any("missing" in record.message.lower() for record in caplog.records)

    def test_ensure_headers_no_warning_when_all_headers_present(self, caplog):
        """No warning when all JOURNAL_HEADERS are present (even with extras)."""
        from backend.services.journal_service import _ensure_headers, JOURNAL_HEADERS

        ws = MagicMock()
        # All expected headers present, plus an extra column
        ws.row_values.return_value = JOURNAL_HEADERS + ["extra_column"]

        with caplog.at_level(logging.WARNING, logger="backend.services.journal_service"):
            _ensure_headers(ws)

        warning_records = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "missing" in r.message.lower()
        ]
        assert warning_records == [], (
            "No missing-headers warning expected when all headers are present"
        )
