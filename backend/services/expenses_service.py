"""
expenses_service.py – CRUD operations for the 'expenses' sheet.

Supports two field layouts (auto-detected from incoming data):

Old layout:
  expense_id | deal_id | expense_type | amount | vat | amount_without_vat | created_at

New layout:
  expense_id | date | category | amount_with_vat | vat_rate | vat_amount
             | amount_without_vat | created_by | deal_id | created_at

The service writes both legacy and new fields when possible so existing readers
continue to work.

Automatic calculations (new layout):
  amount_without_vat = amount_with_vat / (1 + vat_rate)
  vat_amount         = amount_with_vat - amount_without_vat

Public API
----------
add_expense(data, user, role) → dict
get_expenses(deal_id=None, expense_type=None) → List[dict]
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.sheets_service import (
    SHEET_EXPENSES,
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

# Old format headers (kept for backward compat)
EXPENSES_HEADERS: List[str] = [
    "expense_id",
    "deal_id",
    "expense_type",
    "amount",
    "vat",
    "amount_without_vat",
    "created_at",
]

# New format headers (superset of old)
EXPENSES_HEADERS_V2: List[str] = [
    "expense_id",
    "date",
    "category",
    "amount_with_vat",
    "vat_rate",
    "vat_amount",
    "amount_without_vat",
    "created_by",
    # backward compat fields kept at the end
    "deal_id",
    "expense_type",
    "amount",
    "vat",
    "created_at",
]

VALID_EXPENSE_TYPES = frozenset(
    {"variable", "production", "logistics", "returns", "extra"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_headers(ws) -> None:
    """Write the canonical header row if the sheet is empty."""
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(EXPENSES_HEADERS_V2, value_input_option="USER_ENTERED")
            logger.info("Created expenses header row (v2).")
    except Exception as exc:
        logger.warning("Could not ensure expenses headers: %s", exc)


def _next_expense_id(ws) -> str:
    """Generate the next sequential expense ID."""
    try:
        col_values = ws.col_values(1)  # expense_id column
        nums = []
        for v in col_values[1:]:  # skip header
            try:
                nums.append(int(v.strip()))
            except (ValueError, AttributeError):
                pass
        return str(max(nums) + 1) if nums else "1"
    except Exception:
        return "1"


def _row_to_dict(header_map: Dict[str, int], row: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for col_name, idx in header_map.items():
        result[col_name] = row[idx] if idx < len(row) else ""
    return result


def _calculate_expense_vat(amount_with_vat: float, vat_rate: float) -> tuple:
    """
    Compute (amount_without_vat, vat_amount) from amount_with_vat and vat_rate.

    vat_rate is expressed as a decimal fraction (e.g. 0.20 for 20%).
    Returns (amount_without_vat, vat_amount) rounded to 2 dp.
    """
    if vat_rate and amount_with_vat:
        amount_without_vat = round(amount_with_vat / (1 + vat_rate), 2)
        vat_amount = round(amount_with_vat - amount_without_vat, 2)
        return amount_without_vat, vat_amount
    return amount_with_vat, 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_expense(
    data: Dict[str, Any],
    user: str = "",
    role: str = "",
) -> dict:
    """
    Append one expense row to the 'expenses' sheet.

    Accepts both old-style keys (amount, vat, expense_type) and new-style keys
    (amount_with_vat, vat_rate, category).  New-style keys take precedence.

    Auto-generates expense_id and created_at.
    Returns the written row as a dict.
    """
    # Resolve category / expense_type (new name takes priority)
    category = str(data.get("category") or data.get("expense_type", "")).strip().lower()
    if category not in VALID_EXPENSE_TYPES:
        raise ValueError(
            f"category/expense_type must be one of: {', '.join(sorted(VALID_EXPENSE_TYPES))}"
        )

    # Resolve amount: new 'amount_with_vat' takes priority over old 'amount'
    amount_with_vat = safe_float(data.get("amount_with_vat") or data.get("amount") or 0)
    vat_rate = safe_float(data.get("vat_rate", 0))

    # Calculate vat_amount and amount_without_vat
    if vat_rate:
        amount_without_vat, vat_amount = _calculate_expense_vat(amount_with_vat, vat_rate)
    else:
        # Fall back to old explicit vat field
        legacy_vat = safe_float(data.get("vat", 0))
        vat_amount = legacy_vat
        amount_without_vat = safe_float(
            data.get("amount_without_vat", amount_with_vat - legacy_vat)
        )

    deal_id = str(data.get("deal_id", "") or "")
    created_by = str(data.get("created_by", "") or user or "")

    try:
        ws = get_worksheet(SHEET_EXPENSES)
    except SheetNotFoundError as exc:
        raise SheetsError(f"Expenses sheet not found: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)

    with _lock:
        expense_id = _next_expense_id(ws)
        now = datetime.now(tz=timezone.utc)
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")

        row_data: Dict[str, Any] = {
            "expense_id": expense_id,
            "date": date_str,
            "category": category,
            "amount_with_vat": str(amount_with_vat),
            "vat_rate": str(vat_rate),
            "vat_amount": str(vat_amount),
            "amount_without_vat": str(amount_without_vat),
            "created_by": created_by,
            # backward compat fields
            "deal_id": deal_id,
            "expense_type": category,
            "amount": str(amount_with_vat),
            "vat": str(vat_amount),
            "created_at": created_at,
        }

        # Build row aligned to actual sheet headers
        max_idx = max(header_map.values(), default=0)
        row: List = [""] * (max_idx + 1)
        for col_name, idx in header_map.items():
            val = row_data.get(col_name, "")
            row[idx] = str(val) if val is not None else ""

        ws.append_row(row, value_input_option="USER_ENTERED")

    result = {
        "expense_id": expense_id,
        "date": date_str,
        "category": category,
        "amount_with_vat": amount_with_vat,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "amount_without_vat": amount_without_vat,
        "created_by": created_by,
        # backward compat
        "deal_id": deal_id,
        "expense_type": category,
        "amount": amount_with_vat,
        "vat": vat_amount,
        "created_at": created_at,
    }

    append_journal_entry(
        telegram_user_id=user,
        full_name=user,
        user_role=role,
        action="add_expense",
        deal_id=deal_id,
        payload_summary=f"category={category} amount_with_vat={amount_with_vat} vat_rate={vat_rate}",
    )

    return result


def get_expenses(
    deal_id: Optional[str] = None,
    expense_type: Optional[str] = None,
) -> List[dict]:
    """
    Return expense rows, optionally filtered by deal_id and/or expense_type/category.
    """
    try:
        ws = get_worksheet(SHEET_EXPENSES)
    except SheetNotFoundError:
        logger.warning("Expenses sheet not found; returning empty list.")
        return []

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    all_rows = ws.get_all_values()

    entries: List[dict] = []
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        if not any(c.strip() for c in row):
            continue
        entry = _row_to_dict(header_map, row)

        if deal_id and entry.get("deal_id", "").strip() != deal_id.strip():
            continue

        # Support filtering by expense_type (old) or category (new)
        if expense_type:
            row_type = (
                entry.get("category") or entry.get("expense_type", "")
            ).strip().lower()
            if row_type != expense_type.strip().lower():
                continue

        entries.append(entry)

    return entries
