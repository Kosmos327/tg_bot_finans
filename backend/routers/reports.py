"""
reports.py – Report download endpoints.

Routes
------
GET /reports/warehouse/{warehouse}  – warehouse billing report
GET /reports/clients                – all-clients billing report
GET /reports/expenses               – expenses report
GET /reports/profit                 – profit / analytics_monthly report

Each route accepts a ?fmt=csv (default) or ?fmt=xlsx query param.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from backend.services import settings_service
from backend.services.reports_service import (
    generate_clients_report,
    generate_expenses_report,
    generate_profit_report,
    generate_warehouse_report,
)
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    REPORT_DOWNLOAD_ROLES,
    check_role,
)
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

_ALLOWED_WAREHOUSES = {"msk", "nsk", "ekb"}
_ALLOWED_FMTS = {"csv", "xlsx"}


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


def _media_type(fmt: str) -> str:
    if fmt == "xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/csv; charset=utf-8-sig"


def _check_access(role: str) -> None:
    if role == NO_ACCESS_ROLE or not check_role(role, REPORT_DOWNLOAD_ROLES):
        raise HTTPException(
            status_code=403,
            detail="Access denied: report download requires operations_director, accounting, or admin role",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/warehouse/{warehouse}")
async def download_warehouse_report(
    warehouse: str,
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download a billing report for a specific warehouse."""
    if warehouse.lower() not in _ALLOWED_WAREHOUSES:
        raise HTTPException(status_code=400, detail=f"Unknown warehouse: {warehouse}")
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail=f"fmt must be csv or xlsx")

    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)

    try:
        content = generate_warehouse_report(warehouse.lower(), fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"billing_{warehouse.lower()}.{fmt.lower()}"
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/clients")
async def download_clients_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download an all-clients billing report."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")

    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)

    try:
        content = generate_clients_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"clients_report.{fmt.lower()}"
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/expenses")
async def download_expenses_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download an expenses report."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")

    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)

    try:
        content = generate_expenses_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"expenses_report.{fmt.lower()}"
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/profit")
async def download_profit_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download a profit / analytics report from analytics_monthly sheet."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")

    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)

    try:
        content = generate_profit_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"profit_report.{fmt.lower()}"
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
