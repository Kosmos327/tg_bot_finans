"""
Tests for services/deal_service.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

import services.deal_service as deal_service_module
from services.deal_service import create_deal, get_deal, update_deal


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_deals_ws(headers: list[str], existing_id_col: list[str] | None = None):
    ws = MagicMock()
    ws.row_values.return_value = headers
    ws.col_values.return_value = existing_id_col or headers[:1]
    return ws


def _make_journal_ws():
    ws = MagicMock()
    ws.row_values.return_value = []  # empty journal
    return ws


# ---------------------------------------------------------------------------
# create_deal
# ---------------------------------------------------------------------------


class TestCreateDeal:
    def test_creates_deal_and_returns_new_id(self):
        headers = ["ID", "Название", "Клиент", "Сумма", "Дата создания", "Статус"]
        deals_ws = _make_deals_ws(headers, ["ID"])  # no existing deals
        journal_ws = _make_journal_ws()

        data = {
            "Название": "Проект А",
            "Клиент": "ООО Клиент",
            "Сумма": "100 000,00",
            "Дата создания": "15.03.2024",
            "Статус": "новая",
        }

        new_id = create_deal(
            deals_ws=deals_ws,
            journal_ws=journal_ws,
            data=data,
            required_fields=["Название", "Клиент", "Сумма"],
            id_prefix="DEAL-",
            user=12345,
        )

        assert new_id == "DEAL-1"
        deals_ws.append_row.assert_called_once()
        # journal is empty so _ensure_journal_headers writes headers first,
        # then the actual entry — 2 append_row calls expected.
        assert journal_ws.append_row.call_count == 2

    def test_raises_value_error_when_required_field_missing(self):
        headers = ["ID", "Название", "Клиент", "Сумма"]
        deals_ws = _make_deals_ws(headers, ["ID"])
        journal_ws = _make_journal_ws()

        data = {"Название": "Проект А"}  # missing Клиент and Сумма

        with pytest.raises(ValueError, match="Клиент"):
            create_deal(
                deals_ws=deals_ws,
                journal_ws=journal_ws,
                data=data,
                required_fields=["Название", "Клиент", "Сумма"],
                id_prefix="DEAL-",
                user=12345,
            )
        deals_ws.append_row.assert_not_called()
        journal_ws.append_row.assert_not_called()

    def test_normalises_amount_and_date(self):
        headers = ["ID", "Название", "Клиент", "Сумма", "Дата создания"]
        deals_ws = _make_deals_ws(headers, ["ID"])
        journal_ws = _make_journal_ws()

        data = {
            "Название": "X",
            "Клиент": "Y",
            "Сумма": "1 500,99",
            "Дата создания": "01.01.2025",
        }

        create_deal(
            deals_ws=deals_ws,
            journal_ws=journal_ws,
            data=data,
            required_fields=["Название", "Клиент", "Сумма"],
            id_prefix="DEAL-",
            user=1,
        )

        appended_row = deals_ws.append_row.call_args[0][0]
        sum_idx = headers.index("Сумма")
        date_idx = headers.index("Дата создания")
        assert appended_row[sum_idx] == "1500.99"
        assert appended_row[date_idx] == "2025-01-01"

    def test_id_increments_from_existing(self):
        headers = ["ID", "Название", "Клиент", "Сумма"]
        deals_ws = _make_deals_ws(headers, ["ID", "DEAL-1", "DEAL-2"])
        journal_ws = _make_journal_ws()

        data = {"Название": "X", "Клиент": "Y", "Сумма": "100"}

        new_id = create_deal(
            deals_ws=deals_ws,
            journal_ws=journal_ws,
            data=data,
            required_fields=["Название", "Клиент", "Сумма"],
            id_prefix="DEAL-",
            user=1,
        )

        assert new_id == "DEAL-3"


# ---------------------------------------------------------------------------
# update_deal
# ---------------------------------------------------------------------------


class TestUpdateDeal:
    def _setup(self):
        headers = ["ID", "Название", "Клиент", "Сумма", "Статус"]
        deals_ws = MagicMock()
        deals_ws.row_values.side_effect = [
            headers,                                    # get_headers call
            headers,                                    # get_headers call in find_row_by_id
            headers,                                    # get_headers call in update_row
            ["DEAL-1", "Старое", "Клиент", "500", "новая"],  # get_row_as_dict
        ]
        deals_ws.col_values.return_value = ["ID", "DEAL-1", "DEAL-2"]
        journal_ws = _make_journal_ws()
        return deals_ws, journal_ws, headers

    def test_preserves_non_edited_fields(self):
        headers = ["ID", "Название", "Клиент", "Сумма", "Статус"]
        deals_ws = MagicMock()

        call_count = [0]

        def row_values_side_effect(row_num):
            call_count[0] += 1
            if call_count[0] < 3:
                return headers
            return ["DEAL-1", "Старое название", "Клиент А", "500", "новая"]

        deals_ws.row_values.side_effect = row_values_side_effect
        deals_ws.col_values.return_value = ["ID", "DEAL-1"]
        journal_ws = _make_journal_ws()

        merged = update_deal(
            deals_ws=deals_ws,
            journal_ws=journal_ws,
            deal_id="DEAL-1",
            updates={"Статус": "закрыта"},
            user=99,
        )

        # Non-edited fields preserved in returned dict
        assert merged["Название"] == "Старое название"
        assert merged["Клиент"] == "Клиент А"
        assert merged["Статус"] == "закрыта"

        # Only Статус cell was written
        deals_ws.update_cell.assert_called_once_with(2, 5, "закрыта")

    def test_raises_key_error_for_unknown_deal(self):
        headers = ["ID", "Название"]
        deals_ws = MagicMock()
        deals_ws.row_values.return_value = headers
        deals_ws.col_values.return_value = ["ID", "DEAL-1"]
        journal_ws = _make_journal_ws()

        with pytest.raises(KeyError, match="DEAL-99"):
            update_deal(
                deals_ws=deals_ws,
                journal_ws=journal_ws,
                deal_id="DEAL-99",
                updates={"Статус": "закрыта"},
                user=1,
            )
        deals_ws.update_cell.assert_not_called()

    def test_raises_value_error_when_id_in_updates(self):
        deals_ws = MagicMock()
        journal_ws = _make_journal_ws()

        with pytest.raises(ValueError, match="ID"):
            update_deal(
                deals_ws=deals_ws,
                journal_ws=journal_ws,
                deal_id="DEAL-1",
                updates={"ID": "DEAL-999"},
                user=1,
            )


# ---------------------------------------------------------------------------
# get_deal
# ---------------------------------------------------------------------------


class TestGetDeal:
    def test_returns_row_dict(self):
        headers = ["ID", "Название", "Сумма"]
        deals_ws = MagicMock()
        deals_ws.row_values.side_effect = [
            headers,  # get_headers for find_row_by_id
            headers,  # get_headers for get_row_as_dict
            ["DEAL-1", "Тест", "200"],  # actual row
        ]
        deals_ws.col_values.return_value = ["ID", "DEAL-1"]

        row = get_deal(deals_ws, "DEAL-1")
        assert row["ID"] == "DEAL-1"
        assert row["Название"] == "Тест"

    def test_raises_key_error_for_missing_deal(self):
        headers = ["ID", "Название"]
        deals_ws = MagicMock()
        deals_ws.row_values.return_value = headers
        deals_ws.col_values.return_value = ["ID"]

        with pytest.raises(KeyError, match="DEAL-5"):
            get_deal(deals_ws, "DEAL-5")
