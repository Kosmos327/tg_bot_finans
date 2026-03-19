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


def _normalize_deal_row_contract(deal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure stable alias contract for deal display fields.

    Keeps backward compatibility by returning both:
      - client / client_name
      - manager / manager_name
      - status / status_name
    """
    def _ensure_alias_pair(short_key: str, name_key: str) -> None:
        short_value = deal.get(short_key)
        name_value = deal.get(name_key)

        if short_value is None and name_value is not None:
            deal[short_key] = name_value
        elif name_value is None and short_value is not None:
            deal[name_key] = short_value

    _ensure_alias_pair("client", "client_name")
    _ensure_alias_pair("manager", "manager_name")
    _ensure_alias_pair("status", "status_name")
    return deal


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
        deals = await read_sql_view(
            db,
            "public.v_api_deals",
            where_clause=where_clause,
            params=params,
            order_by="created_at DESC",
        )
        return [_normalize_deal_row_contract(deal) for deal in deals]
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

    # Resolve created_by_user_id from auth context: integer app_users.id when
    # authenticated via Telegram, None for web/browser mode (no Telegram session).
    created_by_user_id = user_id if isinstance(user_id, int) else None

    # Defensive validation for manager role: resolve the authenticated manager's
    # DB record and use it as the authoritative manager_id, overriding any
    # value submitted by the frontend. This prevents managers from creating deals
    # attributed to a different manager.
    manager_id = body.manager_id
    if role == "manager":
        caller_tid = _get_caller_telegram_id(x_telegram_id, x_telegram_init_data)
        if caller_tid:
            from sqlalchemy import select as _select
            from app.database.models import Manager as _Manager
            mgr_result = await db.execute(
                _select(_Manager).where(_Manager.telegram_user_id == caller_tid)
            )
            mgr = mgr_result.scalar_one_or_none()
            if mgr is not None:
                if manager_id != mgr.id:
                    logger.warning(
                        "create_deal: manager_id mismatch for telegram_id=%s "
                        "(submitted=%s, authenticated=%s) – using authenticated value",
                        caller_tid,
                        manager_id,
                        mgr.id,
                    )
                manager_id = mgr.id

    # Named parameters passed as a plain dict so that call_sql_function_one
    # uses the text() / named-placeholder code path (never exec_driver_sql).
    # Parameter order in the SQL call matches the PostgreSQL function signature
    # of public.api_create_deal exactly:
    #   p_created_by_user_id, p_status_id, p_business_direction_id, p_client_id,
    #   p_manager_id, p_charged_with_vat, p_vat_type_id, p_vat_rate,
    #   p_paid, p_project_start_date, p_project_end_date, p_act_date,
    #   p_variable_expense_1_without_vat, p_variable_expense_2_without_vat,
    #   p_production_expense_without_vat, p_manager_bonus_percent,
    #   p_source_id, p_document_link, p_comment
    #
    # NOTE: p_charged_without_vat does NOT exist in the SQL function signature.
    sql = (
        "SELECT * FROM public.api_create_deal("
        ":created_by_user_id, :status_id, :business_direction_id, :client_id, :manager_id, "
        ":charged_with_vat, :vat_type_id, :vat_rate, "
        ":paid, :project_start_date, :project_end_date, :act_date, "
        ":variable_expense_1_without_vat, :variable_expense_2_without_vat, "
        ":production_expense_without_vat, :manager_bonus_percent, "
        ":source_id, :document_link, :comment"
        ")"
    )

    params = {
        "created_by_user_id": created_by_user_id,
        "status_id": body.status_id,
        "business_direction_id": body.business_direction_id,
        "client_id": body.client_id,
        "manager_id": manager_id,
        "charged_with_vat": body.charged_with_vat,
        "vat_type_id": body.vat_type_id,
        "vat_rate": body.vat_rate,
        "paid": body.paid,
        "project_start_date": body.project_start_date,
        "project_end_date": body.project_end_date,
        "act_date": body.act_date,
        "variable_expense_1_without_vat": body.variable_expense_1_without_vat,
        "variable_expense_2_without_vat": body.variable_expense_2_without_vat,
        "production_expense_without_vat": body.production_expense_without_vat,
        "manager_bonus_percent": body.manager_bonus_percent,
        "source_id": body.source_id,
        "document_link": body.document_link,
        "comment": body.comment,
    }

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
    # p_updated_by_user_id is the FIRST parameter of public.api_pay_deal.
    updated_by_user_id = user_id if isinstance(user_id, int) else None
    params["updated_by_user_id"] = updated_by_user_id
    sql = (
        "SELECT * FROM public.api_pay_deal("
        ":updated_by_user_id, :deal_id, :payment_amount, :payment_date"
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

    deal = _normalize_deal_row_contract(rows[0])

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
