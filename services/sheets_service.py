"""
Low-level Google Sheets utilities.

All public helpers in this module work exclusively through *header names*
rather than hard-coded column indices, so the sheet layout can change freely
without breaking the bot.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Scopes required by the bot
# ---------------------------------------------------------------------------
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ---------------------------------------------------------------------------
# Client creation
# ---------------------------------------------------------------------------

def build_client(service_account_json: str) -> gspread.Client:
    """Return an authenticated *gspread* client from a JSON string.

    Args:
        service_account_json: Full JSON content of the service account key
                              (i.e. the value of GOOGLE_SERVICE_ACCOUNT_JSON).
    """
    try:
        service_account_info = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON contains invalid JSON."
        ) from exc
    creds = Credentials.from_service_account_info(service_account_info, scopes=_SCOPES)
    return gspread.authorize(creds)


def open_spreadsheet(
    client: gspread.Client, spreadsheet_id: str
) -> gspread.Spreadsheet:
    return client.open_by_key(spreadsheet_id)


# ---------------------------------------------------------------------------
# Header mapping
# ---------------------------------------------------------------------------

def get_headers(worksheet: gspread.Worksheet) -> dict[str, int]:
    """
    Return ``{header_name: 0-based column index}`` for the first row.

    Empty cells in the header row are skipped.
    """
    first_row: list[str] = worksheet.row_values(1)
    return {name: idx for idx, name in enumerate(first_row) if name}


# ---------------------------------------------------------------------------
# Row lookup
# ---------------------------------------------------------------------------

def find_row_by_id(
    worksheet: gspread.Worksheet,
    deal_id: str,
    id_column: str,
) -> int | None:
    """
    Return the **1-based** row index of the first row whose *id_column* cell
    equals *deal_id*, or ``None`` if not found.
    """
    headers = get_headers(worksheet)
    if id_column not in headers:
        return None
    col_idx = headers[id_column] + 1  # gspread uses 1-based indices
    col_values: list[str] = worksheet.col_values(col_idx)
    for row_idx, value in enumerate(col_values):
        if row_idx == 0:  # skip header
            continue
        if value == deal_id:
            return row_idx + 1  # 1-based
    return None


# ---------------------------------------------------------------------------
# Row read / write helpers
# ---------------------------------------------------------------------------

def get_row_as_dict(
    worksheet: gspread.Worksheet,
    row_number: int,
    headers: dict[str, int],
) -> dict[str, Any]:
    """
    Return the row at *row_number* (1-based) as ``{header: value}``.

    Missing trailing cells are treated as empty strings.
    """
    row_values: list[str] = worksheet.row_values(row_number)
    result: dict[str, Any] = {}
    for header, col_idx in headers.items():
        result[header] = row_values[col_idx] if col_idx < len(row_values) else ""
    return result


def build_row_values(
    data: dict[str, Any],
    headers: dict[str, int],
) -> list[Any]:
    """
    Convert *data* (``{header: value}``) into an ordered list of cell values
    aligned with *headers*.

    Columns absent from *data* are left as empty strings.
    """
    n_cols = max(headers.values()) + 1 if headers else 0
    row: list[Any] = [""] * n_cols
    for header, col_idx in headers.items():
        if header in data:
            row[col_idx] = data[header]
    return row


def update_row(
    worksheet: gspread.Worksheet,
    row_number: int,
    data: dict[str, Any],
    headers: dict[str, int],
) -> None:
    """
    Overwrite *only* the cells whose headers appear in *data*.
    All other cells in the row are left unchanged.
    """
    for header, value in data.items():
        if header not in headers:
            continue
        col_idx = headers[header] + 1  # gspread 1-based
        worksheet.update_cell(row_number, col_idx, value)


def append_row_by_headers(
    worksheet: gspread.Worksheet,
    data: dict[str, Any],
    headers: dict[str, int],
) -> None:
    """
    Append a new row whose cells are placed according to *headers*.

    Uses ``append_row`` (inserts after the last non-empty row).
    """
    row_values = build_row_values(data, headers)
    worksheet.append_row(row_values, value_input_option="USER_ENTERED")


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

_SUFFIX_RE = re.compile(r"(\d+)$")


def get_next_deal_id(
    worksheet: gspread.Worksheet,
    id_column: str,
    prefix: str,
) -> str:
    """
    Scan all existing IDs in *id_column*, ignore malformed ones, and return
    ``prefix + (max_numeric_suffix + 1)``.

    If no valid IDs are found the returned ID starts at ``prefix + 1``.
    """
    headers = get_headers(worksheet)
    if id_column not in headers:
        return f"{prefix}1"

    col_idx = headers[id_column] + 1
    all_values: list[str] = worksheet.col_values(col_idx)

    max_suffix = 0
    for value in all_values[1:]:  # skip header row
        value = value.strip()
        if not value.startswith(prefix):
            continue
        suffix_part = value[len(prefix):]
        match = _SUFFIX_RE.fullmatch(suffix_part)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))

    return f"{prefix}{max_suffix + 1}"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_number(value: Any) -> str:
    """
    Normalise a number-like value so Google Sheets stores it as a number:

    * Strip surrounding whitespace.
    * Replace comma-decimal separator with a dot.
    * Remove thousands-separator spaces/underscores.
    """
    text = str(value).strip()
    text = text.replace("\u00a0", "").replace(" ", "").replace("_", "")
    text = text.replace(",", ".")
    return text


def normalize_date(value: Any) -> str:
    """
    Normalise a date-like value to ISO-8601 ``YYYY-MM-DD`` format.

    Accepts:
    * ``datetime`` or ``date`` objects
    * strings in ``DD.MM.YYYY``, ``DD/MM/YYYY``, or ``YYYY-MM-DD`` formats

    Returns the original string unchanged if it cannot be parsed.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "strftime"):  # date object
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text  # return as-is if unrecognised


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_required(
    data: dict[str, Any], required_fields: list[str]
) -> list[str]:
    """
    Return a list of field names from *required_fields* that are absent or
    blank in *data*.  An empty list means validation passed.
    """
    missing: list[str] = []
    for field in required_fields:
        val = data.get(field, "")
        if val is None or str(val).strip() == "":
            missing.append(field)
    return missing
