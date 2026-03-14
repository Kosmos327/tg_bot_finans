"""
journal_service.py - Audit journal operations.

Google Sheets support has been removed. The worksheet parameter is kept
for backward compatibility with existing tests (which mock it).

For production use, use app.services.journal_service with PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.sheets_service import append_row_by_headers, get_headers

_COL_DATETIME = "Дата/Время"
_COL_ACTION = "Действие"
_COL_DEAL_ID = "ID сделки"
_COL_USER = "Пользователь"
_COL_DETAILS = "Детали"

_JOURNAL_COLUMNS = [
    _COL_DATETIME,
    _COL_ACTION,
    _COL_DEAL_ID,
    _COL_USER,
    _COL_DETAILS,
]


def add_journal_entry(
    worksheet: Any,
    action: str,
    deal_id: str,
    user: str | int,
    details: str = "",
) -> None:
    """Append one audit record to the journal worksheet."""
    headers = get_headers(worksheet)
    _ensure_journal_headers(worksheet, headers)
    headers = get_headers(worksheet)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry: dict[str, Any] = {
        _COL_DATETIME: now,
        _COL_ACTION: action,
        _COL_DEAL_ID: str(deal_id),
        _COL_USER: str(user),
        _COL_DETAILS: details,
    }
    append_row_by_headers(worksheet, entry, headers)


def _ensure_journal_headers(worksheet: Any, existing_headers: dict[str, int]) -> None:
    """Write the standard journal header row if the sheet is empty."""
    if existing_headers:
        return
    worksheet.append_row(_JOURNAL_COLUMNS, value_input_option="USER_ENTERED")
