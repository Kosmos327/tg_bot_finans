"""
Deals service: role-aware CRUD and aggregation helpers.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.config import (
    ROLE_ACCOUNTANT,
    ROLE_EDITABLE_FIELDS,
    ROLE_HEAD_OF_SALES,
    ROLE_MANAGER,
    ROLE_OPERATIONS_DIRECTOR,
)
from backend.models.schemas import Deal, MeResponse
from backend.services.sheets import (
    append_journal_entry,
    create_deal as sheets_create_deal,
    get_all_deals,
    get_deal_by_id,
    get_deals_by_manager_tg_id,
    update_deal as sheets_update_deal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def filter_deals_for_user(deals: List[Deal], me: MeResponse) -> List[Deal]:
    """Return only the deals this user is allowed to see."""
    if me.role == ROLE_MANAGER:
        return [d for d in deals if d.creator_tg_id == str(me.telegram_id)]
    # accountant, ops, head_of_sales → all deals
    return deals


def strip_forbidden_fields(deal_data: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Remove any fields the role is not allowed to edit."""
    allowed = set(ROLE_EDITABLE_FIELDS.get(role, []))
    return {k: v for k, v in deal_data.items() if k in allowed}


# ---------------------------------------------------------------------------
# CRUD with role enforcement
# ---------------------------------------------------------------------------

def get_deals_for_user(me: MeResponse) -> List[Deal]:
    deals = get_all_deals()
    return filter_deals_for_user(deals, me)


def get_all_deals_service() -> List[Deal]:
    return get_all_deals()


def get_deal_service(deal_id: str, me: MeResponse) -> Optional[Deal]:
    deal = get_deal_by_id(deal_id)
    if not deal:
        return None
    allowed = filter_deals_for_user([deal], me)
    return allowed[0] if allowed else None


def create_deal_service(deal_data: Dict[str, Any], me: MeResponse) -> Deal:
    # enforce field-level permissions
    allowed_data = strip_forbidden_fields(deal_data, me.role)
    allowed_data["creator_tg_id"] = str(me.telegram_id)

    # auto-fill manager name from user's full_name for manager role
    if me.role == ROLE_MANAGER and not allowed_data.get("manager"):
        allowed_data["manager"] = me.full_name

    deal = sheets_create_deal(allowed_data)

    changed = list(allowed_data.keys())
    append_journal_entry(
        tg_id=me.telegram_id,
        role=me.role,
        action="create_deal",
        deal_id=deal.id,
        changed_fields=changed,
        summary=f"Создана сделка {deal.id} – клиент: {deal.client}",
    )
    return deal


def update_deal_service(
    deal_id: str, deal_data: Dict[str, Any], me: MeResponse
) -> Optional[Deal]:
    # check visibility
    existing = get_deal_service(deal_id, me)
    if not existing:
        return None

    allowed_data = strip_forbidden_fields(deal_data, me.role)
    updated = sheets_update_deal(deal_id, allowed_data)

    if updated:
        changed = list(allowed_data.keys())
        append_journal_entry(
            tg_id=me.telegram_id,
            role=me.role,
            action="update_deal",
            deal_id=deal_id,
            changed_fields=changed,
            summary=f"Обновлена сделка {deal_id}: {', '.join(changed)}",
        )
    return updated


# ---------------------------------------------------------------------------
# Dashboard aggregations
# ---------------------------------------------------------------------------

def _safe_float(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except ValueError:
        return 0.0


def build_manager_dashboard(me: MeResponse) -> Dict[str, Any]:
    deals = get_deals_for_user(me)
    in_progress = [d for d in deals if d.status and "завершен" not in d.status.lower()]
    completed = [d for d in deals if d.status and "завершен" in d.status.lower()]
    total_amount = sum(_safe_float(d.amount_with_vat) for d in deals)
    return {
        "total_my_deals": len(deals),
        "in_progress": len(in_progress),
        "completed": len(completed),
        "total_amount": total_amount,
        "deals": [d.model_dump() for d in deals],
    }


def build_accountant_dashboard() -> Dict[str, Any]:
    deals = get_all_deals()
    awaiting = []
    partial = []
    full_paid = []
    for d in deals:
        amount = _safe_float(d.amount_with_vat)
        paid = _safe_float(d.paid)
        if paid <= 0:
            awaiting.append(d)
        elif paid < amount:
            partial.append(d)
        else:
            full_paid.append(d)
    total_receivable = sum(_safe_float(d.amount_with_vat) - _safe_float(d.paid) for d in deals)
    total_paid = sum(_safe_float(d.paid) for d in deals)
    return {
        "awaiting_payment": len(awaiting),
        "partially_paid": len(partial),
        "fully_paid": len(full_paid),
        "total_receivable": max(total_receivable, 0),
        "total_paid": total_paid,
        "deals": [d.model_dump() for d in deals],
    }


def build_operations_dashboard() -> Dict[str, Any]:
    deals = get_all_deals()
    active = [d for d in deals if d.status and "завершен" not in d.status.lower()]
    total_amount = sum(_safe_float(d.amount_with_vat) for d in deals)
    total_paid = sum(_safe_float(d.paid) for d in deals)
    receivable = max(total_amount - total_paid, 0)
    total_expenses = sum(
        _safe_float(d.var_exp1) + _safe_float(d.var_exp2) + _safe_float(d.prod_exp)
        for d in deals
    )
    gross_profit = total_paid - total_expenses

    # Group by manager
    mgr_map: Dict[str, Dict[str, Any]] = {}
    for d in deals:
        mgr = d.manager or "Неизвестно"
        if mgr not in mgr_map:
            mgr_map[mgr] = {"manager": mgr, "deals": 0, "amount": 0.0}
        mgr_map[mgr]["deals"] += 1
        mgr_map[mgr]["amount"] += _safe_float(d.amount_with_vat)

    return {
        "total_deals": len(deals),
        "active_deals": len(active),
        "total_amount": total_amount,
        "total_paid": total_paid,
        "receivable": receivable,
        "total_expenses": total_expenses,
        "gross_profit": gross_profit,
        "deals": [d.model_dump() for d in deals],
        "by_manager": list(mgr_map.values()),
    }


def build_sales_dashboard() -> Dict[str, Any]:
    deals = get_all_deals()
    in_progress = [d for d in deals if d.status and "завершен" not in d.status.lower()]
    new_deals = [d for d in deals if d.status and "новая" in d.status.lower()]
    completed = [d for d in deals if d.status and "завершен" in d.status.lower()]
    total_amount = sum(_safe_float(d.amount_with_vat) for d in deals)
    avg = total_amount / len(deals) if deals else 0.0

    mgr_map: Dict[str, Dict[str, Any]] = {}
    for d in deals:
        mgr = d.manager or "Неизвестно"
        if mgr not in mgr_map:
            mgr_map[mgr] = {"manager": mgr, "deals": 0, "amount": 0.0, "completed": 0}
        mgr_map[mgr]["deals"] += 1
        mgr_map[mgr]["amount"] += _safe_float(d.amount_with_vat)
        if d.status and "завершен" in d.status.lower():
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
        "deals": [d.model_dump() for d in deals],
    }
