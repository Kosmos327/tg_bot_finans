"""
deal_service.py - Deal CRUD operations.

Google Sheets support has been removed. The Google Sheets worksheet parameters
are kept in function signatures for backward compatibility with existing tests,
but they are treated as mock-compatible objects.

For production use, use app.services.deal_service with PostgreSQL instead.
"""

from __future__ import annotations

from typing import Any

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
from services import journal_service

_COL_ID = "ID"
_COL_DATE_CREATED = "Дата создания"
_COL_AMOUNT = "Сумма"
_NUMBER_FIELDS = {_COL_AMOUNT}
_DATE_FIELDS = {_COL_DATE_CREATED}


def create_deal(
    deals_ws: Any,
    journal_ws: Any,
    data: dict[str, Any],
    required_fields: list[str],
    id_prefix: str,
    user: str | int,
) -> str:
    missing = validate_required(data, required_fields)
    if missing:
        raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing)}")

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
    deals_ws: Any,
    journal_ws: Any,
    deal_id: str,
    updates: dict[str, Any],
    user: str | int,
) -> dict[str, Any]:
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


def get_deal(deals_ws: Any, deal_id: str) -> dict[str, Any]:
    row_number = find_row_by_id(deals_ws, deal_id, _COL_ID)
    if row_number is None:
        raise KeyError(f"Сделка с ID '{deal_id}' не найдена.")

    headers = get_headers(deals_ws)
    return get_row_as_dict(deals_ws, row_number, headers)


def _normalise_fields(data: dict[str, Any]) -> dict[str, Any]:
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
