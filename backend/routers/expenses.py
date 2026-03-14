"""
expenses.py – Expense management endpoints.

Routes
------
POST /expenses            – add a new expense
POST /expenses/bulk       – add multiple expenses in one request
GET  /expenses            – list expenses (optional filters: deal_id, expense_type)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.models.schemas import ExpenseCreate, ExpenseBulkCreate, ExpenseResponse
from backend.services import settings_service
from backend.services.expenses_service import add_expense, add_expenses_bulk, get_expenses
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    EXPENSE_ADD_ROLES,
    FINANCE_VIEW_ROLES,
    check_role,
)
from backend.services.sheets_service import SheetsError
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["expenses"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_user(init_data: Optional[str], role_header: Optional[str] = None) -> tuple:
    if init_data:
        user = extract_user_from_init_data(init_data)
        if user:
            user_id = str(user.get("id", ""))
            role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
            full_name = settings_service.get_user_full_name(user_id) if user_id else ""
            return user_id, role, full_name

    if role_header and role_header.strip():
        from backend.services.permissions import ALLOWED_ROLES
        role = role_header.strip().lower()
        if role in ALLOWED_ROLES:
            return "", role, ""

    return "", NO_ACCESS_ROLE, ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=Dict[str, Any])
async def create_expense(
    body: ExpenseCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Add a new expense record to the 'expenses' sheet.

    Accepts both old-style keys (expense_type, amount, vat) and new-style keys
    (category_level_1, category_level_2, comment, amount_with_vat, vat_rate).

    Accessible by: manager, accounting, operations_director, admin.
    """
    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, EXPENSE_ADD_ROLES):
        raise HTTPException(status_code=403, detail="Access denied")

    expense_data = body.model_dump(exclude_none=True)
    # Ensure created_by is set to the requesting user when not provided
    if "created_by" not in expense_data:
        expense_data["created_by"] = user_id or full_name or role

    try:
        result = add_expense(
            data=expense_data,
            user=user_id or full_name or role,
            role=role,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error adding expense: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/bulk", response_model=List[Dict[str, Any]])
async def create_expenses_bulk(
    body: ExpenseBulkCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Add multiple expense rows in a single request (bulk entry mode).

    Each row in the 'rows' list is validated and written independently.
    The first invalid row causes the entire request to fail with a 422 error
    that identifies the row index.

    Accessible by: manager, accounting, operations_director, admin.
    """
    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, EXPENSE_ADD_ROLES):
        raise HTTPException(status_code=403, detail="Access denied")

    actor = user_id or full_name or role
    rows_data = []
    for row in body.rows:
        row_dict = row.model_dump(exclude_none=True)
        if "created_by" not in row_dict:
            row_dict["created_by"] = actor
        rows_data.append(row_dict)

    try:
        results = add_expenses_bulk(rows=rows_data, user=actor, role=role)
        return results
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error adding bulk expenses: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=List[Dict[str, Any]])
async def list_expenses(
    deal_id: Optional[str] = Query(default=None),
    expense_type: Optional[str] = Query(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    List expense records.

    Accessible by: accounting, operations_director, admin.
    Managers may only list expenses for their own deals (pass ?deal_id=...).
    """
    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    can_view_all = check_role(role, FINANCE_VIEW_ROLES) or check_role(role, EXPENSE_ADD_ROLES)
    if not can_view_all:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return get_expenses(deal_id=deal_id, expense_type=expense_type)
    except SheetsError as exc:
        logger.error("Sheets error listing expenses: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
