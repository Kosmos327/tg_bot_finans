"""
month_close.py – Month closing / archiving endpoints.

Routes
------
POST /month/archive          – call public.archive_month(...)
POST /month/cleanup          – call public.cleanup_month(...)
POST /month/close            – call public.close_month(...)
GET  /month/archive-batches  – read from public.archive_batches
GET  /month/archived-deals   – read from public.v_archived_deals
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.schemas.month_close import (
    ArchiveMonthRequest,
    CleanupMonthRequest,
    CloseMonthRequest,
)
from backend.services.db_exec import call_sql_function, read_sql_view
from backend.services.miniapp_auth_service import get_user_by_telegram_id, get_role_code
from backend.services.permissions import NO_ACCESS_ROLE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/month", tags=["month-close"])

# Roles allowed to perform month-close operations
_MONTH_CLOSE_ROLES = ("operations_director", "admin")


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


def _require_month_close_role(role: str) -> None:
    if role not in _MONTH_CLOSE_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Access denied: only operations_director or admin can perform month-close operations",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/archive", response_model=List[Dict[str, Any]])
async def archive_month(
    body: ArchiveMonthRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Archive a month via public.archive_month(year, month, dry_run).

    dry_run=true runs the check without making changes.
    Accessible by: operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")
    _require_month_close_role(role)

    sql = "SELECT * FROM public.archive_month(:year, :month, :dry_run)"
    params = {"year": body.year, "month": body.month, "dry_run": body.dry_run}

    try:
        return await call_sql_function(db, sql, params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/cleanup", response_model=List[Dict[str, Any]])
async def cleanup_month(
    body: CleanupMonthRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Clean up staging data for a month via public.cleanup_month(year, month).

    Accessible by: operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")
    _require_month_close_role(role)

    sql = "SELECT * FROM public.cleanup_month(:year, :month)"
    params = {"year": body.year, "month": body.month}

    try:
        return await call_sql_function(db, sql, params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/close", response_model=List[Dict[str, Any]])
async def close_month(
    body: CloseMonthRequest,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Close a month via public.close_month(year, month, comment).

    Accessible by: operations_director, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")
    _require_month_close_role(role)

    sql = "SELECT * FROM public.close_month(:year, :month, :comment)"
    params = {"year": body.year, "month": body.month, "comment": body.comment}

    try:
        return await call_sql_function(db, sql, params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/archive-batches", response_model=List[Dict[str, Any]])
async def get_archive_batches(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return archive batch records from public.archive_batches.

    Accessible by: operations_director, accounting, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")
    if role not in ("operations_director", "accounting", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    where_parts: list[str] = []
    params: dict = {}
    if year is not None:
        where_parts.append("year = :year")
        params["year"] = year
    if month is not None:
        where_parts.append("month = :month")
        params["month"] = month

    try:
        return await read_sql_view(
            db,
            "public.archive_batches",
            where_clause=" AND ".join(where_parts),
            params=params,
            order_by="created_at DESC",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/archived-deals", response_model=List[Dict[str, Any]])
async def get_archived_deals(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return archived deals from public.v_archived_deals.

    Accessible by: operations_director, accounting, admin.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")
    if role not in ("operations_director", "accounting", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    where_parts: list[str] = []
    params: dict = {}
    if year is not None:
        where_parts.append("archive_year = :year")
        params["year"] = year
    if month is not None:
        where_parts.append("archive_month = :month")
        params["month"] = month

    try:
        return await read_sql_view(
            db,
            "public.v_archived_deals",
            where_clause=" AND ".join(where_parts),
            params=params,
            order_by="archived_at DESC",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
