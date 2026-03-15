"""
billing_sql.py – Billing endpoints using PostgreSQL SQL functions and views.

Routes
------
GET  /billing/v2         – read from public.v_api_billing
POST /billing/v2/upsert  – call public.api_upsert_billing_entry(...)
POST /billing/v2/pay     – call public.api_pay_billing_entry(...)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.schemas.billing import BillingUpsertRequest, BillingPayRequest
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
