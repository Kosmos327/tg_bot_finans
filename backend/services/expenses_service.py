"""
expenses_service.py – CRUD operations for the 'expenses' sheet.

Expected sheet headers:
  expense_id | deal_id | expense_type | amount | vat | amount_without_vat | created_at

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

EXPENSES_HEADERS: List[str] = [
    "expense_id",
    "deal_id",
    "expense_type",
    "amount",
    "vat",
    "amount_without_vat",
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
            ws.append_row(EXPENSES_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created expenses header row.")
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

    Auto-generates expense_id and created_at.
    Returns the written row as a dict.
    """
    expense_type = str(data.get("expense_type", "")).strip().lower()
    if expense_type not in VALID_EXPENSE_TYPES:
        raise ValueError(
            f"expense_type must be one of: {', '.join(sorted(VALID_EXPENSE_TYPES))}"
        )

    amount = safe_float(data.get("amount", 0))
    vat = safe_float(data.get("vat", 0))
    amount_without_vat = safe_float(data.get("amount_without_vat", amount - vat))

    try:
        ws = get_worksheet(SHEET_EXPENSES)
    except SheetNotFoundError as exc:
        raise SheetsError(f"Expenses sheet not found: {exc}") from exc

    _ensure_headers(ws)

    with _lock:
        expense_id = _next_expense_id(ws)
        created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = [
            expense_id,
            str(data.get("deal_id", "") or ""),
            expense_type,
            str(amount),
            str(vat),
            str(amount_without_vat),
            created_at,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    result = {
        "expense_id": expense_id,
        "deal_id": str(data.get("deal_id", "") or ""),
        "expense_type": expense_type,
        "amount": amount,
        "vat": vat,
        "amount_without_vat": amount_without_vat,
        "created_at": created_at,
    }

    append_journal_entry(
        telegram_user_id=user,
        full_name=user,
        user_role=role,
        action="add_expense",
        deal_id=str(data.get("deal_id", "") or ""),
        payload_summary=f"type={expense_type} amount={amount}",
    )

    return result


def get_expenses(
    deal_id: Optional[str] = None,
    expense_type: Optional[str] = None,
) -> List[dict]:
    """
    Return expense rows, optionally filtered by deal_id and/or expense_type.
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
        if expense_type and entry.get("expense_type", "").strip().lower() != expense_type.strip().lower():
            continue

        entries.append(entry)

    return entries
