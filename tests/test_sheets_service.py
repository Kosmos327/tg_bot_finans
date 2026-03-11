"""
Tests for services/sheets_service.py

We use ``unittest.mock`` to avoid real Google Sheets API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.sheets_service import (
    append_row_by_headers,
    build_row_values,
    find_row_by_id,
    get_headers,
    get_next_deal_id,
    get_row_as_dict,
    normalize_date,
    normalize_number,
    update_row,
    validate_required,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _ws_with_first_row(headers: list[str]) -> MagicMock:
    ws = MagicMock()
    ws.row_values.return_value = headers
    return ws


# ---------------------------------------------------------------------------
# get_headers
# ---------------------------------------------------------------------------


class TestGetHeaders:
    def test_returns_name_to_index_mapping(self):
        ws = _ws_with_first_row(["ID", "Название", "Сумма"])
        result = get_headers(ws)
        assert result == {"ID": 0, "Название": 1, "Сумма": 2}

    def test_skips_empty_header_cells(self):
        ws = _ws_with_first_row(["ID", "", "Сумма"])
        result = get_headers(ws)
        assert "" not in result
        assert result["ID"] == 0
        assert result["Сумма"] == 2

    def test_empty_sheet_returns_empty_dict(self):
        ws = _ws_with_first_row([])
        assert get_headers(ws) == {}


# ---------------------------------------------------------------------------
# find_row_by_id
# ---------------------------------------------------------------------------


class TestFindRowById:
    def test_finds_existing_id(self):
        ws = MagicMock()
        # row_values(1) returns headers
        ws.row_values.return_value = ["ID", "Название"]
        # col_values(1) returns the id column including header
        ws.col_values.return_value = ["ID", "DEAL-1", "DEAL-2", "DEAL-3"]

        row = find_row_by_id(ws, "DEAL-2", "ID")
        assert row == 3  # 1-based, header=1, DEAL-1=2, DEAL-2=3

    def test_returns_none_for_missing_id(self):
        ws = MagicMock()
        ws.row_values.return_value = ["ID", "Название"]
        ws.col_values.return_value = ["ID", "DEAL-1"]

        row = find_row_by_id(ws, "DEAL-99", "ID")
        assert row is None

    def test_returns_none_when_id_column_absent(self):
        ws = MagicMock()
        ws.row_values.return_value = ["Название", "Сумма"]

        row = find_row_by_id(ws, "DEAL-1", "ID")
        assert row is None


# ---------------------------------------------------------------------------
# get_row_as_dict
# ---------------------------------------------------------------------------


class TestGetRowAsDict:
    def test_maps_values_to_headers(self):
        ws = MagicMock()
        ws.row_values.return_value = ["DEAL-1", "Тест", "1000"]
        headers = {"ID": 0, "Название": 1, "Сумма": 2}

        result = get_row_as_dict(ws, 2, headers)
        assert result == {"ID": "DEAL-1", "Название": "Тест", "Сумма": "1000"}

    def test_trailing_missing_cells_become_empty_string(self):
        ws = MagicMock()
        ws.row_values.return_value = ["DEAL-1", "Тест"]  # no Сумма cell
        headers = {"ID": 0, "Название": 1, "Сумма": 2}

        result = get_row_as_dict(ws, 2, headers)
        assert result["Сумма"] == ""


# ---------------------------------------------------------------------------
# build_row_values
# ---------------------------------------------------------------------------


class TestBuildRowValues:
    def test_positions_values_correctly(self):
        headers = {"ID": 0, "Название": 1, "Сумма": 2}
        data = {"ID": "DEAL-5", "Сумма": "500"}
        row = build_row_values(data, headers)
        assert row == ["DEAL-5", "", "500"]

    def test_empty_data_returns_all_empty(self):
        headers = {"ID": 0, "Название": 1}
        row = build_row_values({}, headers)
        assert row == ["", ""]

    def test_empty_headers_returns_empty_list(self):
        assert build_row_values({"ID": "x"}, {}) == []


# ---------------------------------------------------------------------------
# update_row
# ---------------------------------------------------------------------------


class TestUpdateRow:
    def test_calls_update_cell_for_each_field(self):
        ws = MagicMock()
        ws.row_values.return_value = ["ID", "Название", "Сумма"]
        headers = {"ID": 0, "Название": 1, "Сумма": 2}
        data = {"Название": "Новое", "Сумма": "999"}

        update_row(ws, 3, data, headers)

        ws.update_cell.assert_any_call(3, 2, "Новое")  # col 2 = Название
        ws.update_cell.assert_any_call(3, 3, "999")     # col 3 = Сумма
        assert ws.update_cell.call_count == 2

    def test_skips_fields_not_in_headers(self):
        ws = MagicMock()
        headers = {"ID": 0}
        update_row(ws, 2, {"НеСуществует": "x"}, headers)
        ws.update_cell.assert_not_called()


# ---------------------------------------------------------------------------
# append_row_by_headers
# ---------------------------------------------------------------------------


class TestAppendRowByHeaders:
    def test_calls_append_row_with_correct_values(self):
        ws = MagicMock()
        ws.row_values.return_value = ["ID", "Название", "Сумма"]
        headers = {"ID": 0, "Название": 1, "Сумма": 2}
        data = {"ID": "DEAL-1", "Название": "Тест", "Сумма": "100"}

        append_row_by_headers(ws, data, headers)

        ws.append_row.assert_called_once_with(
            ["DEAL-1", "Тест", "100"], value_input_option="USER_ENTERED"
        )


# ---------------------------------------------------------------------------
# get_next_deal_id
# ---------------------------------------------------------------------------


class TestGetNextDealId:
    def test_continues_from_max_suffix(self):
        ws = MagicMock()
        ws.row_values.return_value = ["ID"]
        ws.col_values.return_value = ["ID", "DEAL-1", "DEAL-3", "DEAL-2"]

        nid = get_next_deal_id(ws, "ID", "DEAL-")
        assert nid == "DEAL-4"

    def test_starts_at_1_when_no_existing_ids(self):
        ws = MagicMock()
        ws.row_values.return_value = ["ID"]
        ws.col_values.return_value = ["ID"]

        nid = get_next_deal_id(ws, "ID", "DEAL-")
        assert nid == "DEAL-1"

    def test_ignores_malformed_ids(self):
        ws = MagicMock()
        ws.row_values.return_value = ["ID"]
        ws.col_values.return_value = ["ID", "DEAL-abc", "DEAL-", "bad", "DEAL-5"]

        nid = get_next_deal_id(ws, "ID", "DEAL-")
        assert nid == "DEAL-6"

    def test_returns_prefix_1_when_id_column_absent(self):
        ws = MagicMock()
        ws.row_values.return_value = ["Название", "Сумма"]

        nid = get_next_deal_id(ws, "ID", "DEAL-")
        assert nid == "DEAL-1"


# ---------------------------------------------------------------------------
# normalize_number
# ---------------------------------------------------------------------------


class TestNormalizeNumber:
    @pytest.mark.parametrize(
        "inp, expected",
        [
            ("1 000,50", "1000.50"),
            ("1_000.50", "1000.50"),
            ("  3,14  ", "3.14"),
            ("42", "42"),
            (1234, "1234"),
        ],
    )
    def test_various_formats(self, inp, expected):
        assert normalize_number(inp) == expected


# ---------------------------------------------------------------------------
# normalize_date
# ---------------------------------------------------------------------------


class TestNormalizeDate:
    @pytest.mark.parametrize(
        "inp, expected",
        [
            ("15.03.2024", "2024-03-15"),
            ("15/03/2024", "2024-03-15"),
            ("2024-03-15", "2024-03-15"),
        ],
    )
    def test_supported_formats(self, inp, expected):
        assert normalize_date(inp) == expected

    def test_unrecognised_returns_original(self):
        assert normalize_date("not-a-date") == "not-a-date"

    def test_datetime_object(self):
        from datetime import datetime

        dt = datetime(2024, 3, 15, 10, 30)
        assert normalize_date(dt) == "2024-03-15"


# ---------------------------------------------------------------------------
# validate_required
# ---------------------------------------------------------------------------


class TestValidateRequired:
    def test_returns_empty_when_all_present(self):
        data = {"Название": "Test", "Клиент": "Client", "Сумма": "100"}
        assert validate_required(data, ["Название", "Клиент", "Сумма"]) == []

    def test_returns_missing_fields(self):
        data = {"Название": "Test"}
        missing = validate_required(data, ["Название", "Клиент", "Сумма"])
        assert set(missing) == {"Клиент", "Сумма"}

    def test_blank_string_counts_as_missing(self):
        data = {"Название": "  ", "Клиент": "", "Сумма": "100"}
        missing = validate_required(data, ["Название", "Клиент", "Сумма"])
        assert set(missing) == {"Название", "Клиент"}

    def test_none_counts_as_missing(self):
        data = {"Название": None}
        missing = validate_required(data, ["Название"])
        assert missing == ["Название"]
