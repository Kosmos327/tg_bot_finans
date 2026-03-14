"""
sheets_service.py – Low-level Google Sheets client and reusable header-mapping helpers.

Responsibilities:
  - Initialise the gspread client from GOOGLE_SERVICE_ACCOUNT_JSON env var.
  - Expose helper functions used by the higher-level service modules.

Public helpers
--------------
get_spreadsheet()             – return the target gspread.Spreadsheet
get_worksheet(name)           – return a named worksheet (raises SheetNotFoundError)
get_header_map(sheet)         – {column_name: 0-based_index}
get_required_column(hmap, n)  – index or raises MissingHeaderError
row_to_dict(hmap, row)        – list → dict keyed by header names
dict_to_row(hmap, payload, ordered_headers) – dict → list in header order
"""

import json
import logging
from typing import Dict, List

import gspread
from google.oauth2.service_account import Credentials

from config.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_DEALS = "Учёт сделок"
SHEET_SETTINGS = "Настройки"
SHEET_JOURNAL = "Журнал действий"

# New sheet names for updated Google Sheets structure
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
# Custom exceptions
# ---------------------------------------------------------------------------


class SheetsError(Exception):
    """Base class for Google Sheets service errors."""


class SheetNotFoundError(SheetsError):
    """Raised when a requested worksheet does not exist."""


class MissingHeaderError(SheetsError):
    """Raised when a required column header is absent from a sheet."""


class BadCredentialsError(SheetsError):
    """Raised when the service-account credentials cannot be loaded."""


# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------


def _get_client() -> gspread.Client:
    """Create and return an authorised gspread client using GOOGLE_SERVICE_ACCOUNT_JSON."""
    raw_json = settings.google_service_account_json
    if not raw_json:
        raise BadCredentialsError(
            "GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set. "
            "It must contain the full JSON content of the service account key."
        )
    try:
        service_account_info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise BadCredentialsError(
            "GOOGLE_SERVICE_ACCOUNT_JSON contains invalid JSON. "
            "Ensure the variable holds the complete service account key as JSON."
        ) from exc
    try:
        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as exc:
        raise BadCredentialsError(
            f"Failed to initialise Google Sheets client from service account info: {exc}"
        ) from exc


def get_spreadsheet() -> gspread.Spreadsheet:
    """Return the configured Google Spreadsheet."""
    try:
        client = _get_client()
        return client.open_by_key(settings.google_sheets_spreadsheet_id)
    except BadCredentialsError:
        raise
    except gspread.exceptions.SpreadsheetNotFound as exc:
        raise SheetsError(
            f"Spreadsheet not found: {settings.google_sheets_spreadsheet_id}"
        ) from exc
    except Exception as exc:
        raise SheetsError(f"Failed to open spreadsheet: {exc}") from exc


def get_worksheet(name: str) -> gspread.Worksheet:
    """Return a worksheet by name, raising SheetNotFoundError if absent."""
    try:
        return get_spreadsheet().worksheet(name)
    except gspread.exceptions.WorksheetNotFound as exc:
        raise SheetNotFoundError(f"Sheet '{name}' not found in spreadsheet") from exc


def get_or_create_worksheet(name: str, rows: int = 1000, cols: int = 30) -> gspread.Worksheet:
    """Return a worksheet by name, creating it with a header row if it does not exist."""
    try:
        return get_spreadsheet().worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        logger.info("Sheet '%s' not found; creating it.", name)
        try:
            spreadsheet = get_spreadsheet()
            return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)
        except Exception as exc:
            raise SheetsError(f"Failed to create sheet '{name}': {exc}") from exc


# ---------------------------------------------------------------------------
# Header-mapping helpers (pure-ish, only need the worksheet for reading)
# ---------------------------------------------------------------------------


def get_header_map(sheet: gspread.Worksheet) -> Dict[str, int]:
    """
    Read the first row of *sheet* and return a dict mapping each non-empty
    header name to its 0-based column index.

    Example: {"ID сделки": 0, "Статус сделки": 1, ...}
    """
    try:
        header_row: List[str] = sheet.row_values(1)
    except Exception as exc:
        raise SheetsError(f"Failed to read header row from '{sheet.title}': {exc}") from exc

    return {
        cell.strip(): idx
        for idx, cell in enumerate(header_row)
        if cell.strip()
    }


def get_required_column(header_map: Dict[str, int], column_name: str) -> int:
    """
    Return the 0-based index of *column_name*.
    Raises MissingHeaderError with a clear message if the column is absent.
    """
    if column_name not in header_map:
        available = ", ".join(f"'{k}'" for k in sorted(header_map))
        raise MissingHeaderError(
            f"Required column '{column_name}' not found. "
            f"Available columns: [{available}]"
        )
    return header_map[column_name]


def row_to_dict(header_map: Dict[str, int], row_values: List[str]) -> Dict[str, str]:
    """
    Convert a row (list of cell values) to a dict keyed by header name.

    Columns present in *header_map* but beyond the length of *row_values* are
    returned as empty strings (safe for short rows).
    """
    result: Dict[str, str] = {}
    for col_name, idx in header_map.items():
        result[col_name] = row_values[idx] if idx < len(row_values) else ""
    return result


def dict_to_row(
    header_map: Dict[str, int],
    payload: dict,
    ordered_headers: List[str],
) -> List:
    """
    Convert *payload* to a list ordered by *ordered_headers* using *header_map*.

    Only the columns listed in *ordered_headers* are written; the returned list
    has length equal to the highest column index in *ordered_headers* + 1.

    Values of None are normalised to "".
    """
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


# ---------------------------------------------------------------------------
# Normalisation helpers (pure functions – easy to unit-test)
# ---------------------------------------------------------------------------


def normalise_header(name: str) -> str:
    """Strip and lower-case a header name for case-insensitive comparison."""
    return name.strip().lower()


def safe_float(value: str) -> float:
    """
    Convert *value* to float, returning 0.0 on failure.
    Handles strings like "1 000,50" (spaces as thousands separator, comma as decimal).
    """
    if value is None:
        return 0.0
    cleaned = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def safe_optional_float(value: str):
    """Return float or None if *value* is empty/missing."""
    if not value or str(value).strip() == "":
        return None
    return safe_float(value)
