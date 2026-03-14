"""
sheets_service.py - Deprecated. Google Sheets support has been removed.

This module is kept as a stub for backward compatibility with existing code
that imports from it. All functions raise NotImplementedError at runtime.

For PostgreSQL-based data access, use app.database and app.crud modules.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Stub type for gspread.Worksheet (no longer a real dependency)
# ---------------------------------------------------------------------------

class _WorksheetStub:
    """Placeholder type - gspread is no longer installed."""


# ---------------------------------------------------------------------------
# Normalisation helpers (pure functions, kept for backward compatibility)
# ---------------------------------------------------------------------------


def normalize_number(value: Any) -> str:
    """Normalise a number-like value to a plain decimal string."""
    text = str(value).strip()
    text = text.replace("\u00a0", "").replace(" ", "").replace("_", "")
    text = text.replace(",", ".")
    return text


def normalize_date(value: Any) -> str:
    """Normalise a date-like value to ISO-8601 YYYY-MM-DD format."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def validate_required(data: dict[str, Any], required_fields: list[str]) -> list[str]:
    """Return list of required fields that are absent or blank in data."""
    missing: list[str] = []
    for field in required_fields:
        val = data.get(field, "")
        if val is None or str(val).strip() == "":
            missing.append(field)
    return missing


def build_client(service_account_json: str) -> Any:
    """Stub – raises NotImplementedError. Google Sheets support removed."""
    raise NotImplementedError(
        "Google Sheets support has been removed. "
        "Use PostgreSQL via app.database and app.crud instead."
    )


def open_spreadsheet(client: Any, spreadsheet_id: str) -> Any:
    """Stub – raises NotImplementedError. Google Sheets support removed."""
    raise NotImplementedError(
        "Google Sheets support has been removed. "
        "Use PostgreSQL via app.database and app.crud instead."
    )


def get_headers(worksheet: Any) -> dict[str, int]:
    """Return header map from worksheet. Kept for legacy test compatibility."""
    first_row: list[str] = worksheet.row_values(1)
    return {name: idx for idx, name in enumerate(first_row) if name}


def find_row_by_id(worksheet: Any, deal_id: str, id_column: str) -> int | None:
    """Find row by ID. Kept for legacy test compatibility."""
    headers = get_headers(worksheet)
    if id_column not in headers:
        return None
    col_idx = headers[id_column] + 1
    col_values: list[str] = worksheet.col_values(col_idx)
    for row_idx, value in enumerate(col_values):
        if row_idx == 0:
            continue
        if value == deal_id:
            return row_idx + 1
    return None


def get_row_as_dict(worksheet: Any, row_number: int, headers: dict[str, int]) -> dict[str, Any]:
    """Return row as dict. Kept for legacy test compatibility."""
    row_values: list[str] = worksheet.row_values(row_number)
    result: dict[str, Any] = {}
    for header, col_idx in headers.items():
        result[header] = row_values[col_idx] if col_idx < len(row_values) else ""
    return result


def build_row_values(data: dict[str, Any], headers: dict[str, int]) -> list[Any]:
    """Convert data dict to row list. Kept for legacy test compatibility."""
    n_cols = max(headers.values()) + 1 if headers else 0
    row: list[Any] = [""] * n_cols
    for header, col_idx in headers.items():
        if header in data:
            row[col_idx] = data[header]
    return row


def update_row(worksheet: Any, row_number: int, data: dict[str, Any], headers: dict[str, int]) -> None:
    """Update row cells. Kept for legacy test compatibility."""
    for header, value in data.items():
        if header not in headers:
            continue
        col_idx = headers[header] + 1
        worksheet.update_cell(row_number, col_idx, value)


def append_row_by_headers(worksheet: Any, data: dict[str, Any], headers: dict[str, int]) -> None:
    """Append row. Kept for legacy test compatibility."""
    row_values = build_row_values(data, headers)
    worksheet.append_row(row_values, value_input_option="USER_ENTERED")


_SUFFIX_RE = re.compile(r"(\d+)$")


def get_next_deal_id(worksheet: Any, id_column: str, prefix: str) -> str:
    """Get next deal ID. Kept for legacy test compatibility."""
    headers = get_headers(worksheet)
    if id_column not in headers:
        return f"{prefix}1"
    col_idx = headers[id_column] + 1
    all_values: list[str] = worksheet.col_values(col_idx)
    max_suffix = 0
    for value in all_values[1:]:
        value = value.strip()
        if not value.startswith(prefix):
            continue
        suffix_part = value[len(prefix):]
        match = _SUFFIX_RE.fullmatch(suffix_part)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))
    return f"{prefix}{max_suffix + 1}"
