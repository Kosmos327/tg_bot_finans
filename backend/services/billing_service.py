"""
billing_service.py – CRUD operations for billing_msk / billing_nsk / billing_ekb sheets.

Sheet structure (header row):
  client_name
  p1_shipments_amount, p1_units, p1_storage_amount, p1_pallets,
  p1_returns_amount, p1_returns_trips, p1_extra_services, p1_penalties,
  p1_total_without_penalties, p1_total_with_penalties
  p2_shipments_amount, p2_units, p2_storage_amount, p2_pallets,
  p2_returns_amount, p2_returns_trips, p2_extra_services, p2_penalties,
  p2_total_without_penalties, p2_total_with_penalties

Totals are calculated automatically:
  total_without_penalties = shipments_amount + storage_amount + returns_amount + extra_services
  total_with_penalties    = total_without_penalties - penalties

Public API
----------
get_billing_entries(warehouse)               → List[dict]
get_billing_entry(warehouse, client_name)    → dict | None
upsert_billing_entry(warehouse, entry_data, user, role) → dict
mark_payment(deal_id, payment_amount, user, role) → bool
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.sheets_service import (
    BILLING_SHEETS,
    MissingHeaderError,
    SheetsError,
    SheetNotFoundError,
    get_worksheet,
    get_header_map,
    safe_float,
)
from backend.services.journal_service import append_journal_entry

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

# All expected sheet headers in order
BILLING_HEADERS: List[str] = [
    "client_name",
    "p1_shipments_amount", "p1_units", "p1_storage_amount", "p1_pallets",
    "p1_returns_amount", "p1_returns_trips", "p1_extra_services", "p1_penalties",
    "p1_total_without_penalties", "p1_total_with_penalties",
    "p2_shipments_amount", "p2_units", "p2_storage_amount", "p2_pallets",
    "p2_returns_amount", "p2_returns_trips", "p2_extra_services", "p2_penalties",
    "p2_total_without_penalties", "p2_total_with_penalties",
]

# Fields that are auto-calculated (never written from request data directly)
_CALC_FIELDS = frozenset({
    "p1_total_without_penalties", "p1_total_with_penalties",
    "p2_total_without_penalties", "p2_total_with_penalties",
})

# Sum components for "total without penalties" per period
_SUM_FIELDS_P1 = [
    "p1_shipments_amount", "p1_storage_amount",
    "p1_returns_amount", "p1_extra_services",
]
_SUM_FIELDS_P2 = [
    "p2_shipments_amount", "p2_storage_amount",
    "p2_returns_amount", "p2_extra_services",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_sheet_name(warehouse: str) -> str:
    """Return the sheet name for the given warehouse key (msk/nsk/ekb)."""
    key = warehouse.strip().lower()
    sheet_name = BILLING_SHEETS.get(key)
    if not sheet_name:
        raise ValueError(
            f"Unknown warehouse '{warehouse}'. Must be one of: "
            + ", ".join(sorted(BILLING_SHEETS.keys()))
        )
    return sheet_name


def _calc_totals(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate and inject auto-computed total fields into *row_dict* in-place.

    Returns the same dict (modified).
    """
    for prefix, sum_fields, total_key, with_key, pen_key in [
        ("p1", _SUM_FIELDS_P1, "p1_total_without_penalties",
         "p1_total_with_penalties", "p1_penalties"),
        ("p2", _SUM_FIELDS_P2, "p2_total_without_penalties",
         "p2_total_with_penalties", "p2_penalties"),
    ]:
        total = sum(safe_float(row_dict.get(f, 0)) for f in sum_fields)
        penalties = safe_float(row_dict.get(pen_key, 0))
        row_dict[total_key] = round(total, 2)
        row_dict[with_key] = round(total - penalties, 2)
    return row_dict


def _ensure_headers(ws) -> None:
    """Write the canonical header row if the sheet is empty."""
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(BILLING_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created billing header row in '%s'.", ws.title)
    except Exception as exc:
        logger.warning("Could not ensure billing headers in '%s': %s", ws.title, exc)


def _row_to_dict(header_map: Dict[str, int], row: List[str]) -> Dict[str, Any]:
    """Convert a sheet row to a dict keyed by header names."""
    result: Dict[str, Any] = {}
    for col_name, idx in header_map.items():
        val = row[idx] if idx < len(row) else ""
        result[col_name] = val
    return result


def _dict_to_row(header_map: Dict[str, int], data: Dict[str, Any]) -> List:
    """Convert a data dict to a list aligned with *header_map*."""
    max_idx = max(header_map.values(), default=0)
    row: List = [""] * (max_idx + 1)
    for col_name, idx in header_map.items():
        val = data.get(col_name, "")
        row[idx] = "" if val is None else str(val)
    return row


def _find_client_row(ws, client_name: str, header_map: Dict[str, int]) -> Optional[int]:
    """
    Return the 1-based row index for the row whose client_name matches.
    Returns None if not found.
    """
    client_col_idx = header_map.get("client_name")
    if client_col_idx is None:
        return None
    col_values = ws.col_values(client_col_idx + 1)  # gspread is 1-based
    for i, val in enumerate(col_values):
        if i == 0:
            continue  # skip header
        if val.strip() == client_name.strip():
            return i + 1  # 1-based row
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_billing_entries(warehouse: str) -> List[dict]:
    """Return all billing rows for the given warehouse."""
    sheet_name = _resolve_sheet_name(warehouse)
    try:
        ws = get_worksheet(sheet_name)
    except SheetNotFoundError:
        logger.warning("Billing sheet '%s' not found; returning empty list.", sheet_name)
        return []

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    all_rows = ws.get_all_values()
    entries: List[dict] = []
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        if not any(c.strip() for c in row):
            continue  # skip empty rows
        entry = _row_to_dict(header_map, row)
        entry = _calc_totals(entry)
        entries.append(entry)
    return entries


def get_billing_entry(warehouse: str, client_name: str) -> Optional[dict]:
    """Return the billing row for a specific client in the given warehouse."""
    entries = get_billing_entries(warehouse)
    for e in entries:
        if e.get("client_name", "").strip() == client_name.strip():
            return e
    return None


def upsert_billing_entry(
    warehouse: str,
    entry_data: Dict[str, Any],
    user: str = "",
    role: str = "",
) -> dict:
    """
    Create or update a billing row for *entry_data["client_name"]* in *warehouse*.

    Auto-calculated totals are computed before writing.
    Journal entry is appended after a successful write.

    Returns the final row dict (with calculated totals).
    """
    sheet_name = _resolve_sheet_name(warehouse)
    try:
        ws = get_worksheet(sheet_name)
    except SheetNotFoundError as exc:
        raise SheetsError(f"Billing sheet '{sheet_name}' not found") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)

    client_name = str(entry_data.get("client_name", "")).strip()
    if not client_name:
        raise ValueError("client_name is required")

    # Strip out calculated fields from incoming data (we recalculate them)
    cleaned: Dict[str, Any] = {
        k: v for k, v in entry_data.items()
        if k not in _CALC_FIELDS
    }

    # Recalculate totals
    _calc_totals(cleaned)

    with _lock:
        row_num = _find_client_row(ws, client_name, header_map)
        row_data = _dict_to_row(header_map, cleaned)

        if row_num is None:
            # Append new row
            ws.append_row(row_data, value_input_option="USER_ENTERED")
            action = "create_billing_entry"
        else:
            # Update existing row
            last_col_letter = _col_letter(len(row_data) - 1)
            ws.update(
                f"A{row_num}:{last_col_letter}{row_num}",
                [row_data],
                value_input_option="USER_ENTERED",
            )
            action = "update_billing_entry"

    append_journal_entry(
        telegram_user_id=user,
        full_name=user,
        user_role=role,
        action=action,
        deal_id=client_name,
        payload_summary=f"warehouse={warehouse} client={client_name}",
    )

    return cleaned


def _col_letter(col_index: int) -> str:
    """Convert a 0-based column index to a spreadsheet column letter."""
    result = ""
    n = col_index + 1
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result
