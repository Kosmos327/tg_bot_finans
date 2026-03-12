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
    in_progress = [d for d in deals if d.get("status") and "завершен" not in d["status"].lower()]
    completed = [d for d in deals if d.get("status") and "завершен" in d["status"].lower()]
    total_amount = sum(_safe_float(d.get("charged_with_vat")) for d in deals)
    return {
        "total_my_deals": len(deals),
        "in_progress": len(in_progress),
        "completed": len(completed),
        "total_amount": total_amount,
    }


def _build_accountant_summary(deals: List[dict]) -> Dict[str, Any]:
    awaiting, partial, full_paid = [], [], []
    for d in deals:
        amount = _safe_float(d.get("charged_with_vat"))
        paid = _safe_float(d.get("paid"))
        if paid <= 0:
            awaiting.append(d)
        elif paid < amount:
            partial.append(d)
        else:
            full_paid.append(d)
    total_receivable = sum(
        _safe_float(d.get("charged_with_vat")) - _safe_float(d.get("paid")) for d in deals
    )
    total_paid = sum(_safe_float(d.get("paid")) for d in deals)
    return {
        "awaiting_payment": len(awaiting),
        "partially_paid": len(partial),
        "fully_paid": len(full_paid),
        "total_receivable": max(total_receivable, 0),
        "total_paid": total_paid,
        "total_deals": len(deals),
    }


def _build_operations_summary(deals: List[dict]) -> Dict[str, Any]:
    active = [d for d in deals if d.get("status") and "завершен" not in d["status"].lower()]
    total_amount = sum(_safe_float(d.get("charged_with_vat")) for d in deals)
    total_paid = sum(_safe_float(d.get("paid")) for d in deals)
    receivable = max(total_amount - total_paid, 0)
    total_expenses = sum(
        _safe_float(d.get("variable_expense_1"))
        + _safe_float(d.get("variable_expense_2"))
        + _safe_float(d.get("general_production_expense"))
        for d in deals
    )
    gross_profit = total_paid - total_expenses

    mgr_map: Dict[str, Dict[str, Any]] = {}
    for d in deals:
        mgr = d.get("manager") or "Неизвестно"
        if mgr not in mgr_map:
            mgr_map[mgr] = {"manager": mgr, "deals": 0, "amount": 0.0}
        mgr_map[mgr]["deals"] += 1
        mgr_map[mgr]["amount"] += _safe_float(d.get("charged_with_vat"))

    return {
        "total_deals": len(deals),
        "active_deals": len(active),
        "total_amount": total_amount,
        "total_paid": total_paid,
        "receivable": receivable,
        "total_expenses": total_expenses,
        "gross_profit": gross_profit,
        "by_manager": list(mgr_map.values()),
    }


def _build_sales_summary(deals: List[dict]) -> Dict[str, Any]:
    in_progress = [d for d in deals if d.get("status") and "завершен" not in d["status"].lower()]
    new_deals = [d for d in deals if d.get("status") and "нов" in d["status"].lower()]
    completed = [d for d in deals if d.get("status") and "завершен" in d["status"].lower()]
    total_amount = sum(_safe_float(d.get("charged_with_vat")) for d in deals)
    avg = total_amount / len(deals) if deals else 0.0

    mgr_map: Dict[str, Dict[str, Any]] = {}
    for d in deals:
        mgr = d.get("manager") or "Неизвестно"
        if mgr not in mgr_map:
            mgr_map[mgr] = {"manager": mgr, "deals": 0, "amount": 0.0, "completed": 0}
        mgr_map[mgr]["deals"] += 1
        mgr_map[mgr]["amount"] += _safe_float(d.get("charged_with_vat"))
        if d.get("status") and "завершен" in d["status"].lower():
            mgr_map[mgr]["completed"] += 1

    for v in mgr_map.values():
        v["avg"] = v["amount"] / v["deals"] if v["deals"] else 0.0

    return {
        "deals_in_progress": len(in_progress),
        "new_deals": len(new_deals),
        "completed_deals": len(completed),
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
