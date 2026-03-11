"""
Deal service — high-level CRUD operations for the "Сделки" sheet.

All writes go through ``sheets_service`` helpers so they are always driven
by header names rather than hard-coded column indices.
"""

from __future__ import annotations

from typing import Any

import gspread

from services import journal_service
from services.sheets_service import (
    append_row_by_headers,
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
# Column names – only used as *constants* for the ID column and date/number
# columns that require normalisation.  All other fields are passed through
# as-is from the caller.
# ---------------------------------------------------------------------------

_COL_ID = "ID"
_COL_DATE_CREATED = "Дата создания"
_COL_AMOUNT = "Сумма"

# Fields that contain numeric values and must be normalised before writing.
_NUMBER_FIELDS = {_COL_AMOUNT}

# Fields that contain dates and must be normalised before writing.
_DATE_FIELDS = {_COL_DATE_CREATED}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_deal(
    deals_ws: gspread.Worksheet,
    journal_ws: gspread.Worksheet,
    data: dict[str, Any],
    required_fields: list[str],
    id_prefix: str,
    user: str | int,
) -> str:
    """
    Validate, normalise, and append a new deal row.

    Parameters
    ----------
    deals_ws:
        The "Сделки" worksheet.
    journal_ws:
        The "Журнал действий" worksheet.
    data:
        Field values keyed by column header name.
    required_fields:
        List of field names that must be non-blank.
    id_prefix:
        Prefix for auto-generated IDs (e.g. ``"DEAL-"``).
    user:
        Telegram user ID or username for the audit log.

    Returns
    -------
    str
        The new deal ID.

    Raises
    ------
    ValueError
        If required fields are missing.
    """
    missing = validate_required(data, required_fields)
    if missing:
        raise ValueError(
            f"Отсутствуют обязательные поля: {', '.join(missing)}"
        )

    data = _normalise_fields(data)

    headers = get_headers(deals_ws)
    new_id = get_next_deal_id(deals_ws, _COL_ID, id_prefix)
    data[_COL_ID] = new_id

    append_row_by_headers(deals_ws, data, headers)

    journal_service.add_journal_entry(
        worksheet=journal_ws,
        action="создание",
        deal_id=new_id,
        user=user,
        details=_format_details(data),
    )

    return new_id


def update_deal(
    deals_ws: gspread.Worksheet,
    journal_ws: gspread.Worksheet,
    deal_id: str,
    updates: dict[str, Any],
    user: str | int,
) -> dict[str, Any]:
    """
    Update specific fields of an existing deal while preserving all others.

    Parameters
    ----------
    deals_ws:
        The "Сделки" worksheet.
    journal_ws:
        The "Журнал действий" worksheet.
    deal_id:
        The ID of the deal to update.
    updates:
        Only the fields that should change, keyed by column header name.
    user:
        Telegram user ID or username for the audit log.

    Returns
    -------
    dict
        The full updated row as ``{header: value}``.

    Raises
    ------
    KeyError
        If no deal with *deal_id* is found.
    ValueError
        If *updates* tries to overwrite the ID column.
    """
    if _COL_ID in updates:
        raise ValueError("Обновление поля ID запрещено.")

    row_number = find_row_by_id(deals_ws, deal_id, _COL_ID)
    if row_number is None:
        raise KeyError(f"Сделка с ID '{deal_id}' не найдена.")

    headers = get_headers(deals_ws)
    existing = get_row_as_dict(deals_ws, row_number, headers)

    normalised_updates = _normalise_fields(updates)

    merged = {**existing, **normalised_updates}

    update_row(deals_ws, row_number, normalised_updates, headers)

    journal_service.add_journal_entry(
        worksheet=journal_ws,
        action="обновление",
        deal_id=deal_id,
        user=user,
        details=_format_details(normalised_updates),
    )

    return merged


def get_deal(
    deals_ws: gspread.Worksheet,
    deal_id: str,
) -> dict[str, Any]:
    """
    Return the deal row as ``{header: value}``.

    Raises
    ------
    KeyError
        If no deal with *deal_id* is found.
    """
    row_number = find_row_by_id(deals_ws, deal_id, _COL_ID)
    if row_number is None:
        raise KeyError(f"Сделка с ID '{deal_id}' не найдена.")

    headers = get_headers(deals_ws)
    return get_row_as_dict(deals_ws, row_number, headers)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with numbers and dates normalised."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in _NUMBER_FIELDS:
            result[key] = normalize_number(value)
        elif key in _DATE_FIELDS:
            result[key] = normalize_date(value)
        else:
            result[key] = value
    return result


def _format_details(data: dict[str, Any]) -> str:
    return "; ".join(f"{k}={v}" for k, v in data.items() if k != _COL_ID)
