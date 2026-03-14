"""
reports.py – Report download endpoints.

Routes
------
GET /reports/warehouse/{warehouse}  – warehouse billing report
GET /reports/clients                – all-clients billing report
GET /reports/expenses               – expenses report
GET /reports/profit                 – profit / analytics_monthly report
GET /reports/warehouse-revenue      – aggregated warehouse revenue with VAT totals
GET /reports/paid-deals             – deals that have been fully paid
GET /reports/unpaid-deals           – deals that have not been fully paid
GET /reports/paid-billing           – billing entries marked as paid
GET /reports/unpaid-billing         – billing entries not yet paid
GET /reports/billing-by-month       – billing entries for a specific month (?month=YYYY-MM)
GET /reports/billing-by-client      – billing entries for a specific client (?client=NAME)

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
    generate_warehouse_revenue_report,
    generate_paid_deals_report,
    generate_unpaid_deals_report,
    generate_paid_billing_report,
    generate_unpaid_billing_report,
    generate_billing_by_month_report,
    generate_billing_by_client_report,
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
    """Download a profit report with VAT totals, revenue without VAT, and gross profit."""
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


@router.get("/warehouse-revenue")
async def download_warehouse_revenue_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """
    Download an aggregated warehouse revenue report.

    Includes total_with_vat, total_vat, total_without_vat per client/warehouse.
    """
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")

    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)

    try:
        content = generate_warehouse_revenue_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"warehouse_revenue_report.{fmt.lower()}"
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/paid-deals")
async def download_paid_deals_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download a report of fully paid deals."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)
    try:
        content = generate_paid_deals_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename=paid_deals.{fmt.lower()}"},
    )


@router.get("/unpaid-deals")
async def download_unpaid_deals_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download a report of unpaid or partially paid deals."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)
    try:
        content = generate_unpaid_deals_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename=unpaid_deals.{fmt.lower()}"},
    )


@router.get("/paid-billing")
async def download_paid_billing_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download a report of paid billing entries across all warehouses."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)
    try:
        content = generate_paid_billing_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename=paid_billing.{fmt.lower()}"},
    )


@router.get("/unpaid-billing")
async def download_unpaid_billing_report(
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download a report of unpaid billing entries across all warehouses."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)
    try:
        content = generate_unpaid_billing_report(fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename=unpaid_billing.{fmt.lower()}"},
    )


@router.get("/billing-by-month")
async def download_billing_by_month_report(
    month: str = Query(..., description="Month in YYYY-MM format"),
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download billing entries for a specific month (YYYY-MM)."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)
    try:
        content = generate_billing_by_month_report(month=month, fmt=fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    safe_month = month.replace("/", "-").replace("..", "")
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename=billing_{safe_month}.{fmt.lower()}"},
    )


@router.get("/billing-by-client")
async def download_billing_by_client_report(
    client: str = Query(..., description="Client name"),
    fmt: str = Query(default="csv"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Response:
    """Download billing entries for a specific client across all warehouses."""
    if fmt.lower() not in _ALLOWED_FMTS:
        raise HTTPException(status_code=400, detail="fmt must be csv or xlsx")
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)
    _check_access(role)
    try:
        content = generate_billing_by_client_report(client=client, fmt=fmt.lower())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=_media_type(fmt.lower()),
        headers={"Content-Disposition": f"attachment; filename=billing_client.{fmt.lower()}"},
    )
