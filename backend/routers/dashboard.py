"""Dashboard router – role-aware aggregated data."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.services import deals_service, settings_service
from backend.services.db_exec import read_sql_view
from backend.services.miniapp_auth_service import get_user_by_telegram_id, get_role_code, resolve_user_from_init_data
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    FINANCE_VIEW_ROLES,
    ALLOWED_ROLES,
    can_see_all_deals,
    check_role,
)
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _resolve_user(
    init_data: Optional[str], role_header: Optional[str] = None
) -> tuple:
    """Return (user_id, role, full_name) from Telegram initData or X-User-Role header.

    When initData is present but the Sheets-based role lookup returns NO_ACCESS_ROLE
    (user migrated to PostgreSQL-only), fall through to the X-User-Role header so
    that authenticated sessions continue to work.

    Returns:
        - (user_id_str, role_code, full_name) when resolved via initData + Sheets lookup.
        - ("", role_code, "") when resolved via X-User-Role header fallback.
        - ("", NO_ACCESS_ROLE, "") when no auth information can be resolved.
    """
    if init_data:
        user = extract_user_from_init_data(init_data)
        if user:
            user_id = str(user.get("id", ""))
            role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
            full_name = settings_service.get_user_full_name(user_id) if user_id else ""
            if role != NO_ACCESS_ROLE:
                return user_id, role, full_name

    if role_header and role_header.strip():
        role = role_header.strip().lower()
        if role in ALLOWED_ROLES:
            return "", role, ""

    return "", NO_ACCESS_ROLE, ""


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def _build_manager_summary(deals: List[dict]) -> Dict[str, Any]:
    in_progress = 0
    completed = 0
    total_amount = 0.0
    for d in deals:
        status = (d.get("status") or "").lower()
        amount = _safe_float(d.get("charged_with_vat"))
        total_amount += amount
        if "завершен" in status:
            completed += 1
        else:
            in_progress += 1
    return {
        "total_my_deals": len(deals),
        "in_progress": in_progress,
        "completed": completed,
        "total_amount": total_amount,
    }


def _build_accountant_summary(deals: List[dict]) -> Dict[str, Any]:
    awaiting = partial = full_paid = 0
    total_receivable = 0.0
    total_paid = 0.0
    for d in deals:
        amount = _safe_float(d.get("charged_with_vat"))
        paid = _safe_float(d.get("paid"))
        total_paid += paid
        if paid <= 0:
            awaiting += 1
        elif paid < amount:
            partial += 1
        else:
            full_paid += 1
        total_receivable += max(amount - paid, 0)
    return {
        "awaiting_payment": awaiting,
        "partially_paid": partial,
        "fully_paid": full_paid,
        "total_receivable": total_receivable,
        "total_paid": total_paid,
        "total_deals": len(deals),
    }


def _build_operations_summary(deals: List[dict]) -> Dict[str, Any]:
    active = 0
    total_amount = 0.0
    total_paid = 0.0
    total_expenses = 0.0
    mgr_map: Dict[str, Dict[str, Any]] = {}

    for d in deals:
        status = (d.get("status") or "").lower()
        amount = _safe_float(d.get("charged_with_vat"))
        paid = _safe_float(d.get("paid"))
        expenses = (
            _safe_float(d.get("variable_expense_1"))
            + _safe_float(d.get("variable_expense_2"))
            + _safe_float(d.get("general_production_expense"))
        )
        total_amount += amount
        total_paid += paid
        total_expenses += expenses
        if "завершен" not in status:
            active += 1

        mgr = d.get("manager") or "Неизвестно"
        if mgr not in mgr_map:
            mgr_map[mgr] = {"manager": mgr, "deals": 0, "amount": 0.0}
        mgr_map[mgr]["deals"] += 1
        mgr_map[mgr]["amount"] += amount

    return {
        "total_deals": len(deals),
        "active_deals": active,
        "total_amount": total_amount,
        "total_paid": total_paid,
        "receivable": max(total_amount - total_paid, 0),
        "total_expenses": total_expenses,
        "gross_profit": total_paid - total_expenses,
        "by_manager": list(mgr_map.values()),
    }


def _build_sales_summary(deals: List[dict]) -> Dict[str, Any]:
    in_progress = 0
    new_deals = 0
    completed = 0
    total_amount = 0.0
    mgr_map: Dict[str, Dict[str, Any]] = {}

    for d in deals:
        status = (d.get("status") or "").lower()
        amount = _safe_float(d.get("charged_with_vat"))
        total_amount += amount

        if "завершен" in status:
            completed += 1
        else:
            in_progress += 1
        if "нов" in status:
            new_deals += 1

        mgr = d.get("manager") or "Неизвестно"
        if mgr not in mgr_map:
            mgr_map[mgr] = {"manager": mgr, "deals": 0, "amount": 0.0, "completed": 0}
        mgr_map[mgr]["deals"] += 1
        mgr_map[mgr]["amount"] += amount
        if "завершен" in status:
            mgr_map[mgr]["completed"] += 1

    for v in mgr_map.values():
        v["avg"] = v["amount"] / v["deals"] if v["deals"] else 0.0

    avg = total_amount / len(deals) if deals else 0.0
    return {
        "deals_in_progress": in_progress,
        "new_deals": new_deals,
        "completed_deals": completed,
        "total_amount": total_amount,
        "avg_deal_amount": avg,
        "by_manager": list(mgr_map.values()),
    }


@router.get("", response_model=Dict[str, Any])
async def dashboard(
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Return role-aware dashboard payload."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if role == "manager":
            deals = deals_service.get_deals_by_user(full_name) if full_name else []
            data = _build_manager_summary(deals)
        elif role == "accountant":
            deals = deals_service.get_all_deals()
            data = _build_accountant_summary(deals)
        elif role == "operations_director":
            deals = deals_service.get_all_deals()
            data = _build_operations_summary(deals)
        elif role == "head_of_sales":
            deals = deals_service.get_all_deals()
            data = _build_sales_summary(deals)
        else:
            data = {}
    except Exception as exc:
        logger.error("Dashboard error for role %s: %s", role, exc)
        raise HTTPException(status_code=500, detail="Dashboard data unavailable") from exc

    return {"role": role, "full_name": full_name, "data": data}


# ---------------------------------------------------------------------------
# Owner Dashboard helpers
# ---------------------------------------------------------------------------

_PAID_STATUSES = frozenset({"оплачено", "paid", "оплачен"})
_OWNER_ACCESS_ROLES = frozenset({"operations_director", "accounting", "admin"})


def _filter_deals_by_month(deals: List[dict], month: Optional[str]) -> List[dict]:
    """Filter deals by month prefix (YYYY-MM) matched against project_start_date or act_date."""
    if not month:
        return deals
    result = []
    for d in deals:
        date_val = str(d.get("project_start_date") or d.get("act_date") or "")
        if date_val.startswith(month):
            result.append(d)
    return result


def _build_owner_summary(deals: List[dict]) -> Dict[str, Any]:
    """Build owner-level financial aggregation from deals."""
    total_with_vat = 0.0
    total_without_vat = 0.0
    total_expenses = 0.0
    total_paid = 0.0
    client_map: Dict[str, float] = {}

    for d in deals:
        charged = _safe_float(d.get("charged_with_vat"))
        no_vat = _safe_float(d.get("amount_without_vat"))
        paid = _safe_float(d.get("paid"))
        expenses = (
            _safe_float(d.get("variable_expense_1"))
            + _safe_float(d.get("variable_expense_2"))
            + _safe_float(d.get("general_production_expense"))
        )
        total_with_vat += charged
        total_without_vat += no_vat if no_vat else charged
        total_expenses += expenses
        total_paid += paid

        client = d.get("client") or "Неизвестно"
        client_map[client] = client_map.get(client, 0.0) + charged

    total_debt = max(total_with_vat - total_paid, 0.0)
    gross_profit = total_with_vat - total_expenses

    top_clients = sorted(
        [{"client": c, "revenue": r} for c, r in client_map.items()],
        key=lambda x: x["revenue"],
        reverse=True,
    )[:10]

    return {
        "total_revenue_with_vat": total_with_vat,
        "total_revenue_without_vat": total_without_vat,
        "total_expenses": total_expenses,
        "gross_profit": gross_profit,
        "total_debt": total_debt,
        "top_clients": top_clients,
    }


def _build_billing_summary(month: Optional[str]) -> Dict[str, Any]:
    """Build billing-level summary: paid/unpaid counts and warehouse breakdown."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    paid_count = 0
    unpaid_count = 0
    warehouse_breakdown: Dict[str, Dict[str, Any]] = {}

    for wh_key in BILLING_SHEETS:
        try:
            entries = get_billing_entries(wh_key)
        except Exception:
            entries = []

        wh_with_vat = 0.0
        wh_paid = 0
        wh_unpaid = 0

        for e in entries:
            period = str(e.get("period", "")).strip()
            if month and period and not (period == month or period.startswith(f"{month}-")):
                continue

            status = str(e.get("payment_status", "")).strip().lower()
            total = _safe_float(e.get("total_with_vat") or e.get("p1_total_with_penalties"))
            wh_with_vat += total

            if status in _PAID_STATUSES:
                paid_count += 1
                wh_paid += 1
            else:
                unpaid_count += 1
                wh_unpaid += 1

        warehouse_breakdown[wh_key.upper()] = {
            "total_with_vat": wh_with_vat,
            "paid_count": wh_paid,
            "unpaid_count": wh_unpaid,
        }

    return {
        "paid_billing_count": paid_count,
        "unpaid_billing_count": unpaid_count,
        "warehouse_breakdown": warehouse_breakdown,
    }


@router.get("/owner", response_model=Dict[str, Any])
async def owner_dashboard(
    month: Optional[str] = Query(default=None, description="Filter by month (YYYY-MM)"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Aggregated owner-level dashboard.

    Returns financial KPIs from deals and billing sheets, optionally filtered by month.
    Accessible by: operations_director, accounting, admin.
    """
    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, _OWNER_ACCESS_ROLES):
        raise HTTPException(status_code=403, detail="Access denied: owner dashboard requires director, accounting, or admin role")

    try:
        all_deals = deals_service.get_all_deals()
        deals = _filter_deals_by_month(all_deals, month)
        deals_summary = _build_owner_summary(deals)
        billing_summary = _build_billing_summary(month)
    except Exception as exc:
        logger.error("Owner dashboard error: %s", exc)
        raise HTTPException(status_code=500, detail="Owner dashboard data unavailable") from exc

    return {
        "role": role,
        "full_name": full_name,
        "month": month,
        **deals_summary,
        **billing_summary,
    }



# ---------------------------------------------------------------------------
# New SQL-view-based dashboard endpoint
# ---------------------------------------------------------------------------

async def _resolve_user_db(
    db: AsyncSession,
    x_telegram_id: Optional[str],
    x_telegram_init_data: Optional[str] = None,
    x_user_role: Optional[str] = None,
) -> tuple:
    """Resolve (user_id, role, full_name) from app_users with fallback chain.

    1. X-Telegram-Id header → app_users lookup (primary, fastest path).
    2. X-Telegram-Init-Data header → HMAC-validated initData → app_users lookup.
    3. X-User-Role header → role accepted as-is (for sessions that set the role
       in localStorage after a successful /auth/miniapp-login but where the
       telegram_id was not available in the current request context).
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


@router.get("/summary", response_model=List[Dict[str, Any]])
async def dashboard_summary(
    month: Optional[str] = Query(default=None, description="Filter by month YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return summary data from public.v_dashboard_summary.

    Accessible by: operations_director, accounting, admin.
    """
    user_id, role, full_name = await _resolve_user_db(
        db, x_telegram_id, x_telegram_init_data, x_user_role
    )

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied: please login first")

    if role not in ("operations_director", "accounting", "admin"):
        raise HTTPException(status_code=403, detail="Access denied: insufficient role")

    try:
        return await read_sql_view(
            db,
            "public.v_dashboard_summary",
            where_clause="",
            params={},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
