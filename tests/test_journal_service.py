"""
Tests for services/journal_service.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.journal_service import (
    _JOURNAL_COLUMNS,
    add_journal_entry,
)


def _make_ws(existing_headers: list[str] | None = None) -> MagicMock:
    ws = MagicMock()
    # row_values(1) is called by get_headers inside add_journal_entry
    ws.row_values.return_value = existing_headers or []
    return ws


class TestAddJournalEntry:
    def test_appends_entry_when_headers_exist(self):
        ws = _make_ws(["Дата/Время", "Действие", "ID сделки", "Пользователь", "Детали"])

        add_journal_entry(
            worksheet=ws,
            action="создание",
            deal_id="DEAL-1",
            user=42,
            details="Название=Test",
        )

        assert ws.append_row.call_count == 1
        appended = ws.append_row.call_args[0][0]
        assert appended[1] == "создание"
        assert appended[2] == "DEAL-1"
        assert appended[3] == "42"
        assert appended[4] == "Название=Test"

    def test_writes_header_row_when_journal_is_empty(self):
        ws = _make_ws([])  # empty sheet

        add_journal_entry(
            worksheet=ws,
            action="обновление",
            deal_id="DEAL-2",
            user="admin",
        )

        # First call writes headers, second call writes the entry
        assert ws.append_row.call_count == 2
        first_call_args = ws.append_row.call_args_list[0][0][0]
        assert first_call_args == _JOURNAL_COLUMNS

    def test_datetime_is_included_in_entry(self):
        ws = _make_ws(["Дата/Время", "Действие", "ID сделки", "Пользователь", "Детали"])

        add_journal_entry(worksheet=ws, action="создание", deal_id="DEAL-1", user=1)

        appended = ws.append_row.call_args[0][0]
        datetime_str: str = appended[0]
        assert "UTC" in datetime_str  # confirm timezone marker

    def test_user_id_converted_to_string(self):
        ws = _make_ws(["Дата/Время", "Действие", "ID сделки", "Пользователь", "Детали"])

        add_journal_entry(worksheet=ws, action="создание", deal_id="DEAL-1", user=99999)

        appended = ws.append_row.call_args[0][0]
        assert appended[3] == "99999"
