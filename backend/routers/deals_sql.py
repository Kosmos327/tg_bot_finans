"""
deals_sql.py – Deal endpoints using PostgreSQL SQL functions and views.

Routes
------
GET  /deals               – read from public.v_api_deals
POST /deals/create        – call public.api_create_deal(...)
POST /deals/pay           – call public.api_pay_deal(...)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.schemas.deals import DealCreateRequest, DealPayRequest
from backend.services.db_exec import call_sql_function, call_sql_function_one, read_sql_view
from backend.services.miniapp_auth_service import get_user_by_telegram_id, get_role_code
from backend.services.permissions import NO_ACCESS_ROLE, can_see_all_deals

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deals", tags=["deals-sql"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_user(
    db: AsyncSession,
    x_telegram_id: Optional[str],
) -> tuple:
    """
    Resolve (user_id_int, role_code, full_name) from app_users via X-Telegram-Id.
    Returns (None, NO_ACCESS_ROLE, "") on failure.
    """
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
async def list_deals(
    manager_id: Optional[int] = None,
    client_id: Optional[int] = None,
    status_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return deals from public.v_api_deals.

    Managers see only their own deals (filtered by manager_id from app_users).
    Higher roles can see all deals and optionally filter by manager_id / client_id / status_id.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    where_parts: list[str] = []
    params: dict = {}

    if role == "manager":
        # Managers see only their own deals; resolve manager_id from telegram_id
        if x_telegram_id:
            try:
                tid = int(x_telegram_id.strip())
            except (ValueError, TypeError):
                tid = None
            if tid:
                where_parts.append("manager_telegram_id = :tid")
                params["tid"] = tid
    else:
        if manager_id is not None:
            where_parts.append("manager_id = :manager_id")
            params["manager_id"] = manager_id
        if client_id is not None:
            where_parts.append("client_id = :client_id")
            params["client_id"] = client_id
        if status_id is not None:
            where_parts.append("status_id = :status_id")
            params["status_id"] = status_id

    where_clause = " AND ".join(where_parts)

    try:
        return await read_sql_view(
            db,
            "public.v_api_deals",
            where_clause=where_clause,
            params=params,
            order_by="created_at DESC",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/create", response_model=Dict[str, Any])
async def create_deal(
    body: DealCreateRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Create a new deal via public.api_create_deal(...).

    Returns the created deal record.
    Accessible by: manager, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("manager", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    params = body.model_dump()
    # Build the SQL function call with all parameters
    sql = (
        "SELECT * FROM public.api_create_deal("
        ":status_id, :business_direction_id, :client_id, :manager_id, "
        ":charged_with_vat, :charged_without_vat, :vat_type_id, :vat_rate, "
        ":paid, :project_start_date, :project_end_date, :act_date, "
        ":variable_expense_1_without_vat, :variable_expense_2_without_vat, "
        ":production_expense_without_vat, :manager_bonus_percent, "
        ":source_id, :document_link, :comment"
        ")"
    )

    try:
        result = await call_sql_function_one(db, sql, params)
        if result is None:
            raise HTTPException(status_code=500, detail="Deal creation returned no result")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pay", response_model=Dict[str, Any])
async def pay_deal(
    body: DealPayRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Record a payment for a deal via public.api_pay_deal(...).

    Accessible by: accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("accounting", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    params = body.model_dump()
    sql = (
        "SELECT * FROM public.api_pay_deal("
        ":deal_id, :payment_amount, :payment_date"
        ")"
    )

    try:
        result = await call_sql_function_one(db, sql, params)
        if result is None:
            raise HTTPException(status_code=404, detail="Deal not found or payment failed")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
