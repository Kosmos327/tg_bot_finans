"""
expenses_sql.py – Expense endpoints using PostgreSQL SQL functions and views.

Routes
------
GET  /expenses/v2          – read from public.v_api_expenses
POST /expenses/v2/create   – call public.api_create_expense(...)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.schemas.expenses import ExpenseCreateRequest
from backend.services.db_exec import call_sql_function_one, read_sql_view
from backend.services.miniapp_auth_service import get_user_by_telegram_id, get_role_code
from backend.services.permissions import NO_ACCESS_ROLE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses/v2", tags=["expenses-sql"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_user(
    db: AsyncSession,
    x_telegram_id: Optional[str],
) -> tuple:
    if not x_telegram_id:
        return None, NO_ACCESS_ROLE, ""
    try:
        tid = int(x_telegram_id.strip())
    except (ValueError, TypeError):
        return None, NO_ACCESS_ROLE, ""
    user = await get_user_by_telegram_id(db, tid)
    if user is None:
        return None, NO_ACCESS_ROLE, ""
    role = await get_role_code(db, user.role_id)
    return user.id, role or NO_ACCESS_ROLE, user.full_name


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[Dict[str, Any]])
async def list_expenses(
    deal_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """Return expenses from public.v_api_expenses."""
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    where_parts: list[str] = []
    params: dict = {}

    if deal_id is not None:
        where_parts.append("deal_id = :deal_id")
        params["deal_id"] = deal_id

    where_clause = " AND ".join(where_parts)

    try:
        return await read_sql_view(
            db,
            "public.v_api_expenses",
            where_clause=where_clause,
            params=params,
            order_by="created_at DESC",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/create", response_model=Dict[str, Any])
async def create_expense(
    body: ExpenseCreateRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Create a new expense via public.api_create_expense(...).

    Accessible by: manager, accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("manager", "accounting", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    params = body.model_dump()
    # created_by = the user performing the action
    params["created_by"] = str(user_id) if user_id else full_name

    sql = (
        "SELECT * FROM public.api_create_expense("
        ":deal_id, :category_level_1_id, :category_level_2_id, "
        ":amount_without_vat, :vat_type_id, :vat_rate, :comment, :created_by"
        ")"
    )

    try:
        result = await call_sql_function_one(db, sql, params)
        if result is None:
            raise HTTPException(status_code=500, detail="Expense creation returned no result")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
