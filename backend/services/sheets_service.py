"""
sheets_service.py - Deprecated. Google Sheets support has been removed.

This module provides stubs for backward compatibility with existing code.
For PostgreSQL-based data access, use app.database and app.crud modules.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sheet name constants (kept for import compatibility)
# ---------------------------------------------------------------------------

SHEET_DEALS = "Учёт сделок"
SHEET_SETTINGS = "Настройки"
SHEET_JOURNAL = "Журнал действий"
SHEET_DEALS_NEW = "deals"
SHEET_CLIENTS = "clients"
SHEET_MANAGERS = "managers"
SHEET_EXPENSES = "expenses"
SHEET_MANAGER_BONUSES = "manager_bonuses"
SHEET_BILLING_MSK = "billing_msk"
SHEET_BILLING_NSK = "billing_nsk"
SHEET_BILLING_EKB = "billing_ekb"
SHEET_ANALYTICS_MONTHLY = "analytics_monthly"
SHEET_SETTINGS_NEW = "settings"
SHEET_JOURNAL_NEW = "journal"

BILLING_SHEETS = {
    "msk": SHEET_BILLING_MSK,
    "nsk": SHEET_BILLING_NSK,
    "ekb": SHEET_BILLING_EKB,
}


# ---------------------------------------------------------------------------
# Custom exceptions (kept for import compatibility)
# ---------------------------------------------------------------------------


class SheetsError(Exception):
    """Base class for data service errors."""


class SheetNotFoundError(SheetsError):
    """Raised when a requested resource does not exist."""


class MissingHeaderError(SheetsError):
    """Raised when a required column is absent."""


class BadCredentialsError(SheetsError):
    """Raised when credentials cannot be loaded."""


# ---------------------------------------------------------------------------
# Stubs that raise NotImplementedError
# ---------------------------------------------------------------------------


def get_spreadsheet() -> Any:
    raise NotImplementedError(
        "Google Sheets support has been removed. Use PostgreSQL via app.database."
    )


def get_worksheet(name: str) -> Any:
    raise NotImplementedError(
        "Google Sheets support has been removed. Use PostgreSQL via app.database."
    )


def get_or_create_worksheet(name: str, rows: int = 1000, cols: int = 30) -> Any:
    raise NotImplementedError(
        "Google Sheets support has been removed. Use PostgreSQL via app.database."
    )


# ---------------------------------------------------------------------------
# Header-mapping helpers (kept as pure functions for test compatibility)
# ---------------------------------------------------------------------------


def get_header_map(sheet: Any) -> Dict[str, int]:
    """Read header row from a mock/real sheet object."""
    try:
        header_row: List[str] = sheet.row_values(1)
    except Exception as exc:
        raise SheetsError(f"Failed to read header row: {exc}") from exc
    return {
        cell.strip(): idx
        for idx, cell in enumerate(header_row)
        if cell.strip()
    }


def get_required_column(header_map: Dict[str, int], column_name: str) -> int:
    """Return 0-based index of column_name or raise MissingHeaderError."""
    if column_name not in header_map:
        available = ", ".join(f"'{k}'" for k in sorted(header_map))
        raise MissingHeaderError(
            f"Required column '{column_name}' not found. "
            f"Available columns: [{available}]"
        )
    return header_map[column_name]


def row_to_dict(header_map: Dict[str, int], row_values: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for col_name, idx in header_map.items():
        result[col_name] = row_values[idx] if idx < len(row_values) else ""
    return result


def dict_to_row(
    header_map: Dict[str, int],
    payload: dict,
    ordered_headers: List[str],
) -> List:
    if not ordered_headers:
        return []
    max_idx = max(
        (header_map[h] for h in ordered_headers if h in header_map),
        default=0,
    )
    row: List = [""] * (max_idx + 1)
    for col_name in ordered_headers:
        if col_name in header_map and col_name in payload:
            val = payload[col_name]
            row[header_map[col_name]] = val if val is not None else ""
    return row


def normalise_header(name: str) -> str:
    return name.strip().lower()


def safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    cleaned = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def safe_optional_float(value: Any) -> Optional[float]:
    if not value or str(value).strip() == "":
        return None
    return safe_float(value)
