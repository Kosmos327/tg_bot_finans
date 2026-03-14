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
    "category_level_1",
    "category_level_2",
    "comment",
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
# New 2-level category hierarchy
# ---------------------------------------------------------------------------

EXPENSE_CATEGORIES_L1 = frozenset({
    "логистика",
    "наёмный персонал",
    "расходники",
    "другое",
})

EXPENSE_CATEGORIES_L2: Dict[str, frozenset] = {
    "логистика": frozenset({"забор возвратов", "отвоз fbo", "отвоз fbs", "другое"}),
    "наёмный персонал": frozenset({"погрузочно-разгрузочные работы", "упаковка товара", "другое"}),
    "расходники": frozenset({"упаковочный материал", "паллеты", "короба", "пломбы"}),
    "другое": frozenset(),  # free-form, comment required
}

# Level 2 values that require a comment
_COMMENT_REQUIRED_L2 = frozenset({"другое", "упаковочный материал"})


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

def _validate_new_categories(
    cat1: str, cat2: Optional[str], comment: Optional[str]
) -> None:
    """Validate the 2-level category combo and comment requirements."""
    cat1_lower = cat1.strip().lower()
    if cat1_lower not in EXPENSE_CATEGORIES_L1:
        raise ValueError(
            f"category/expense_type must be one of: {', '.join(sorted(EXPENSE_CATEGORIES_L1))}"
        )

    if cat1_lower == "другое" and not (comment and comment.strip()):
        raise ValueError("comment is required when category_level_1 is 'Другое'")

    if cat2:
        cat2_lower = cat2.strip().lower()
        allowed_l2 = EXPENSE_CATEGORIES_L2.get(cat1_lower, frozenset())
        if allowed_l2 and cat2_lower not in allowed_l2:
            raise ValueError(
                f"category_level_2 for '{cat1}' must be one of: "
                + ", ".join(sorted(allowed_l2))
            )
        if cat2_lower in _COMMENT_REQUIRED_L2 and not (comment and comment.strip()):
            raise ValueError(
                f"comment is required when category_level_2 is '{cat2}'"
            )


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

    Accepts:
    - New 2-level category system: category_level_1, category_level_2, comment
    - New single-level: category, amount_with_vat, vat_rate
    - Legacy keys: expense_type, amount, vat

    Auto-generates expense_id and created_at.
    Returns the written row as a dict.
    """
    cat_level_1 = str(data.get("category_level_1") or "").strip()
    cat_level_2 = str(data.get("category_level_2") or "").strip()
    comment = str(data.get("comment") or "").strip()

    if cat_level_1:
        # New 2-level category system
        _validate_new_categories(cat_level_1, cat_level_2 or None, comment or None)
        # Map to legacy category field for backward compat
        cat1_lower = cat_level_1.lower()
        category = cat1_lower
    else:
        # Old single-level category system
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
            "category_level_1": cat_level_1,
            "category_level_2": cat_level_2,
            "comment": comment,
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
        "category_level_1": cat_level_1,
        "category_level_2": cat_level_2,
        "comment": comment,
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
        payload_summary=f"cat1={cat_level_1 or category} cat2={cat_level_2} "
                        f"amount_with_vat={amount_with_vat} vat_rate={vat_rate}",
    )

    return result


def add_expenses_bulk(
    rows: List[Dict[str, Any]],
    user: str = "",
    role: str = "",
) -> List[dict]:
    """
    Add multiple expense rows in a single call.

    Each row is processed by add_expense. Rows are committed sequentially.
    Returns the list of written rows.
    Raises ValueError on the first invalid row (with the row index in the message).
    """
    results: List[dict] = []
    for i, row_data in enumerate(rows):
        try:
            result = add_expense(data=row_data, user=user, role=role)
            results.append(result)
        except ValueError as exc:
            raise ValueError(f"Row {i}: {exc}") from exc
    return results


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
