"""Dashboard router – role-aware aggregated data."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException

from backend.services import deals_service, settings_service
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    can_see_all_deals,
)
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _resolve_user(init_data: Optional[str]) -> tuple:
    """Return (user_id, role, full_name) from Telegram initData."""
    if not init_data:
        return "", NO_ACCESS_ROLE, ""
    user = extract_user_from_init_data(init_data)
    if not user:
        return "", NO_ACCESS_ROLE, ""
    user_id = str(user.get("id", ""))
    role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
    full_name = settings_service.get_user_full_name(user_id) if user_id else ""
    return user_id, role, full_name


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
) -> Dict[str, Any]:
    """Return role-aware dashboard payload."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

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
