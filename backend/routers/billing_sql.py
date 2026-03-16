"""
billing_sql.py – Billing endpoints using PostgreSQL SQL functions and views.

Routes
------
GET  /billing/v2                – read from public.v_api_billing
GET  /billing/v2/search         – search billing entry (ID-based filter)
POST /billing/v2/upsert         – call public.api_upsert_billing_entry(...)
POST /billing/v2/pay            – call public.api_pay_billing_entry(...)
POST /billing/v2/payment/mark   – mark deal payment via public.api_pay_deal(...)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.schemas.billing import BillingUpsertRequest, BillingPayRequest, BillingPaymentMarkRequest
from backend.services.db_exec import call_sql_function_one, read_sql_view
from backend.services.miniapp_auth_service import get_user_by_telegram_id, get_role_code
from backend.services.permissions import NO_ACCESS_ROLE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/v2", tags=["billing-sql"])


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
async def list_billing(
    client_id: Optional[int] = Query(default=None),
    warehouse_id: Optional[int] = Query(default=None),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """Return billing entries from public.v_api_billing."""
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    where_parts: list[str] = []
    params: dict = {}

    if client_id is not None:
        where_parts.append("client_id = :client_id")
        params["client_id"] = client_id
    if warehouse_id is not None:
        where_parts.append("warehouse_id = :warehouse_id")
        params["warehouse_id"] = warehouse_id
    if month is not None:
        where_parts.append("month = :month")
        params["month"] = month

    where_clause = " AND ".join(where_parts)

    try:
        return await read_sql_view(
            db,
            "public.v_api_billing",
            where_clause=where_clause,
            params=params,
            order_by="month DESC",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/upsert", response_model=Dict[str, Any])
async def upsert_billing_entry(
    body: BillingUpsertRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Create or update a billing entry via public.api_upsert_billing_entry(...).

    Accessible by: manager, accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("manager", "accounting", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    params = body.model_dump()

    sql = (
        "SELECT * FROM public.api_upsert_billing_entry("
        ":client_id, :warehouse_id, :month, :period, "
        ":shipments_with_vat, :shipments_without_vat, :units_count, "
        ":storage_with_vat, :storage_without_vat, :pallets_count, "
        ":returns_pickup_with_vat, :returns_pickup_without_vat, :returns_trips_count, "
        ":additional_services_with_vat, :additional_services_without_vat, "
        ":penalties, :vat_type_id, :comment"
        ")"
    )

    try:
        result = await call_sql_function_one(db, sql, params)
        if result is None:
            raise HTTPException(
                status_code=500, detail="Billing upsert returned no result"
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pay", response_model=Dict[str, Any])
async def pay_billing_entry(
    body: BillingPayRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Record a payment for a billing entry via public.api_pay_billing_entry(...).

    Accessible by: accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("accounting", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    params = body.model_dump()

    sql = (
        "SELECT * FROM public.api_pay_billing_entry("
        ":billing_entry_id, :payment_amount, :payment_date"
        ")"
    )

    try:
        result = await call_sql_function_one(db, sql, params)
        if result is None:
            raise HTTPException(
                status_code=404, detail="Billing entry not found or payment failed"
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/search", response_model=Dict[str, Any])
async def search_billing(
    client_id: Optional[int] = Query(default=None),
    warehouse_id: Optional[int] = Query(default=None),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    period: Optional[str] = Query(default=None, description="p1 or p2"),
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Search for a billing entry by client_id, warehouse_id, month, and/or period.

    Returns {"found": true, ...entry fields} if a matching row exists in
    public.v_api_billing, or {"found": false} if no match is found.

    Replaces the legacy GET /billing/search (text-name-based) endpoint for
    callers that have enriched settings (ID-based lookups).

    Accessible by: manager, accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    where_parts: list[str] = []
    params: dict = {}

    if client_id is not None:
        where_parts.append("client_id = :client_id")
        params["client_id"] = client_id
    if warehouse_id is not None:
        where_parts.append("warehouse_id = :warehouse_id")
        params["warehouse_id"] = warehouse_id
    if month is not None:
        where_parts.append("month = :month")
        params["month"] = month
    if period is not None:
        where_parts.append("period = :period")
        params["period"] = period

    if not where_parts:
        raise HTTPException(
            status_code=422,
            detail="At least one filter (client_id, warehouse_id, month, period) is required",
        )

    try:
        rows = await read_sql_view(
            db,
            "public.v_api_billing",
            where_clause=" AND ".join(where_parts),
            params=params,
            order_by="month DESC",
            limit=1,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not rows:
        return {"found": False}

    return {"found": True, **rows[0]}


@router.post("/payment/mark", response_model=Dict[str, Any])
async def mark_deal_payment(
    body: BillingPaymentMarkRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Mark a payment on a deal via public.api_pay_deal(deal_id, payment_amount, payment_date).

    Accepts deal_id as a numeric string (the deal's integer primary key).
    Returns the updated deal record including remaining_amount.

    Replaces the legacy POST /billing/payment/mark (Sheets-based) endpoint.
    Accessible by: accounting, operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("accounting", "operations_director", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    # Resolve deal_id to integer primary key
    try:
        int_deal_id = int(body.deal_id)
    except (ValueError, TypeError):
        # Fall back: look up by deal_id text column in the view
        try:
            rows = await read_sql_view(
                db,
                "public.v_api_deals",
                where_clause="deal_id = :did",
                params={"did": body.deal_id},
                limit=1,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if not rows:
            raise HTTPException(status_code=404, detail="Deal not found")
        int_deal_id = rows[0].get("id")
        if not int_deal_id:
            raise HTTPException(status_code=500, detail="Cannot resolve deal ID to integer")

    sql = "SELECT * FROM public.api_pay_deal(:deal_id, :payment_amount, :payment_date)"
    params = {
        "deal_id": int_deal_id,
        "payment_amount": body.payment_amount,
        "payment_date": body.payment_date,
    }

    try:
        result = await call_sql_function_one(db, sql, params)
        if result is None:
            raise HTTPException(
                status_code=404, detail="Deal not found or payment failed"
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
