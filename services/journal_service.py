"""
Journal service — writes audit entries to the "Журнал действий" sheet.

Every successful create or update of a deal must call ``add_journal_entry``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import gspread

from services.sheets_service import (
    append_row_by_headers,
    get_headers,
)

# Expected columns in the "Журнал действий" worksheet.
# The sheet may have them in any order; we always look them up by name.
_COL_DATETIME = "Дата/Время"
_COL_ACTION = "Действие"
_COL_DEAL_ID = "ID сделки"
_COL_USER = "Пользователь"
_COL_DETAILS = "Детали"


def add_journal_entry(
    worksheet: gspread.Worksheet,
    action: str,
    deal_id: str,
    user: str | int,
    details: str = "",
) -> None:
    """
    Append one audit record to the journal worksheet.

    Parameters
    ----------
    worksheet:
        The "Журнал действий" :class:`gspread.Worksheet`.
    action:
        Human-readable action label, e.g. ``"создание"`` or ``"обновление"``.
    deal_id:
        The identifier of the deal being created or updated.
    user:
        Telegram user ID (integer) or username string.
    details:
        Optional free-text description of what changed.
    """
    headers = get_headers(worksheet)
    _ensure_journal_headers(worksheet, headers)
    # Re-read headers in case they were just created.
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_JOURNAL_COLUMNS = [
    _COL_DATETIME,
    _COL_ACTION,
    _COL_DEAL_ID,
    _COL_USER,
    _COL_DETAILS,
]


def _ensure_journal_headers(
    worksheet: gspread.Worksheet,
    existing_headers: dict[str, int],
) -> None:
    """
    Write the standard journal header row if the sheet is empty.

    If headers already exist they are left unchanged.
    """
    if existing_headers:
        return
    worksheet.append_row(_JOURNAL_COLUMNS, value_input_option="USER_ENTERED")
