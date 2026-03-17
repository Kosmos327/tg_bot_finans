"""
deals_sql.py – Deal endpoints using PostgreSQL SQL functions and views.

Routes
------
GET   /deals                  – read from public.v_api_deals
GET   /deals/{deal_id}        – single deal from public.v_api_deals
POST  /deals/create           – call public.api_create_deal(...)
POST  /deals/pay              – call public.api_pay_deal(...)
PATCH /deals/update/{deal_id} – update deal fields (PG ORM; no SQL function yet)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.models.deal import DealUpdate
from backend.schemas.deals import DealCreateRequest, DealPayRequest
from backend.services.db_exec import call_sql_function, call_sql_function_one, read_sql_view
from backend.services.miniapp_auth_service import get_user_by_telegram_id, get_role_code, resolve_user_from_init_data
from backend.services.permissions import NO_ACCESS_ROLE, ALLOWED_ROLES, can_see_all_deals
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deals", tags=["deals-sql"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_user(
    db: AsyncSession,
    x_telegram_id: Optional[str],
    x_telegram_init_data: Optional[str] = None,
    x_user_role: Optional[str] = None,
) -> tuple:
    """
    Resolve (user_id_int, role_code, full_name) from app_users.

    Fallback chain (first match wins):
      1. X-Telegram-Id header (stored after /auth/miniapp-login).
      2. X-Telegram-Init-Data header (validates HMAC, extracts telegram_id,
         looks up app_users) — used when auto-login has not yet completed.
      3. X-User-Role header — browser/web-mode users who completed role-login
         but have no Telegram context.  Role is accepted as-is after confirming
         it is a known allowed role.

    Returns (None, NO_ACCESS_ROLE, "") on failure.
    """
    if x_telegram_id:
        try:
            tid = int(x_telegram_id.strip())
        except (ValueError, TypeError):
            return None, NO_ACCESS_ROLE, ""

        user = await get_user_by_telegram_id(db, tid)
        if user is None:
            return None, NO_ACCESS_ROLE, ""

        role = await get_role_code(db, user.role_id)
        return user.id, role or NO_ACCESS_ROLE, user.full_name

    if x_telegram_init_data:
        return await resolve_user_from_init_data(db, x_telegram_init_data)

    if x_user_role and x_user_role.strip():
        role = x_user_role.strip().lower()
        if role in ALLOWED_ROLES:
            return "", role, ""

    return None, NO_ACCESS_ROLE, ""


def _get_caller_telegram_id(
    x_telegram_id: Optional[str],
    x_telegram_init_data: Optional[str] = None,
) -> Optional[int]:
    """
    Extract the caller's Telegram user ID from request headers for use in
    role-based deal filtering (managers see only their own deals).

    Tries X-Telegram-Id first, then extracts from X-Telegram-Init-Data.
    NOTE: HMAC validation of initData is done in _resolve_user; this helper
    only extracts the id field for filtering purposes after auth has succeeded.
    """
    if x_telegram_id:
        try:
            return int(x_telegram_id.strip())
        except (ValueError, TypeError):
            pass
    if x_telegram_init_data:
        try:
            user_dict = extract_user_from_init_data(x_telegram_init_data)
            if user_dict:
                raw_id = user_dict.get("id")
                if raw_id is not None:
                    return int(raw_id)
        except (ValueError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[Dict[str, Any]])
async def list_deals(
    manager_id: Optional[int] = None,
    client_id: Optional[int] = None,
    status_id: Optional[int] = None,
    business_direction_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return deals from public.v_api_deals.

    Managers see only their own deals (filtered by manager_id from app_users).
    Higher roles can see all deals and optionally filter by manager_id / client_id /
    status_id / business_direction_id.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    where_parts: list[str] = []
    params: dict = {}

    if role == "manager":
        # Managers see only their own deals; resolve manager_id from telegram_id
        caller_tid = _get_caller_telegram_id(x_telegram_id, x_telegram_init_data)
        if caller_tid:
            where_parts.append("manager_telegram_id = :tid")
            params["tid"] = caller_tid
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
        if business_direction_id is not None:
            where_parts.append("business_direction_id = :business_direction_id")
            params["business_direction_id"] = business_direction_id

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
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Create a new deal via public.api_create_deal(...).

    Returns the created deal record.
    Accessible by: manager, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("manager", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    params = body.model_dump()
    # PARAMETER ORDER IS CRITICAL — asyncpg translates each SQLAlchemy named bind
    # param (:name) into a positional $N placeholder in the order they first appear
    # in this SQL string.  That positional order MUST match the PostgreSQL function
    # signature of public.api_create_deal:
    #   1. p_status_id              2. p_business_direction_id
    #   3. p_client_id              4. p_manager_id
    #   5. p_charged_with_vat       6. p_charged_without_vat
    #   7. p_vat_type_id            8. p_vat_rate
    #   9. p_paid                  10. p_project_start_date
    #  11. p_project_end_date      12. p_act_date
    #  13. p_variable_expense_1_without_vat
    #  14. p_variable_expense_2_without_vat
    #  15. p_production_expense_without_vat
    #  16. p_manager_bonus_percent  17. p_source_id
    #  18. p_document_link         19. p_comment
    #
    # Do NOT reorder these params — swapping :manager_id/:charged_with_vat caused
    # the FK violation "Key (manager_id)=(123) is not present in table managers".
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
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Record a payment for a deal via public.api_pay_deal(...).

    Accessible by: accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)

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


@router.get("/{deal_id}", response_model=Dict[str, Any])
async def get_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Return a single deal from public.v_api_deals.

    Looks up by integer primary key (id) when deal_id is numeric, or falls
    back to matching the deal_id text column for string codes.

    Replaces the legacy GET /deal/{id} endpoint.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    # Try integer lookup first (common case: deal.id stored as str in UI state)
    try:
        int_id = int(deal_id)
        where = "id = :deal_id"
        params: dict = {"deal_id": int_id}
    except (ValueError, TypeError):
        where = "deal_id = :deal_id"
        params = {"deal_id": deal_id}

    try:
        rows = await read_sql_view(
            db,
            "public.v_api_deals",
            where_clause=where,
            params=params,
            limit=1,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=404, detail="Deal not found")

    deal = rows[0]

    # Managers can only view their own deals
    if role == "manager":
        caller_tid = _get_caller_telegram_id(x_telegram_id, x_telegram_init_data)
        if caller_tid and deal.get("manager_telegram_id") != caller_tid:
            raise HTTPException(status_code=403, detail="Access denied")

    return deal


@router.patch("/update/{deal_id}", response_model=Dict[str, Any])
async def update_deal(
    deal_id: str,
    update: DealUpdate,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Update deal fields via PostgreSQL.

    Uses the existing PG-based update service (no api_update_deal() SQL
    function exists yet).  Role-based field filtering is applied server-side.

    Replaces the legacy PATCH /deal/update/{id} endpoint.
    """
    from backend.services import deals_service

    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    # Managers can only edit their own deals
    if role == "manager":
        try:
            int_id = int(deal_id)
            rows = await read_sql_view(
                db, "public.v_api_deals", where_clause="id = :id", params={"id": int_id}, limit=1
            )
        except (ValueError, TypeError):
            rows = []
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if not rows:
            raise HTTPException(status_code=404, detail="Deal not found")

        manager_tid = rows[0].get("manager_telegram_id")
        caller_tid = _get_caller_telegram_id(x_telegram_id, x_telegram_init_data)
        if caller_tid and manager_tid != caller_tid:
            raise HTTPException(status_code=403, detail="Access denied")

    try:
        success = await deals_service.update_deal_pg(
            db=db,
            deal_id=deal_id,
            update_data=update_data,
            telegram_user_id=str(user_id) if user_id else "",
            user_role=role,
            full_name=full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error updating deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    if not success:
        raise HTTPException(status_code=404, detail="Deal not found")

    return {"success": True, "deal_id": deal_id}
