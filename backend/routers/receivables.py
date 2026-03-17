"""
receivables.py – Accounts receivable / debt control endpoints.

Routes
------
GET /receivables          – aggregated debt report (by client, warehouse, month, status)

Formula: debt = total_with_vat - payment_amount

Payment statuses:
  paid          – debt == 0 (fully paid)
  partial       – 0 < payment_amount < total_with_vat
  unpaid        – payment_amount == 0
  overdue       – unpaid or partial (project_end_date in the past)
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.services import settings_service
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    FINANCE_VIEW_ROLES,
    ALLOWED_ROLES,
    check_role,
)
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receivables", tags=["receivables"])

_PAID_STATUSES = frozenset({"оплачено", "paid", "оплачен"})
_WAREHOUSES = ("msk", "nsk", "ekb")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_user(init_data: Optional[str], role_header: Optional[str] = None) -> tuple:
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


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).strip().replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _payment_status(total: float, paid: float, end_date: str) -> str:
    """Determine the payment status label."""
    debt = total - paid
    if debt <= 0:
        return "paid"
    if paid > 0:
        return "partial"
    # Determine if overdue: unpaid and end_date < today
    if end_date:
        try:
            end = date.fromisoformat(str(end_date)[:10])
            if end < date.today():
                return "overdue"
        except (ValueError, TypeError):
            pass
    return "unpaid"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("", response_model=Dict[str, Any])
async def get_receivables(
    month: Optional[str] = Query(default=None, description="Filter by month (YYYY-MM)"),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Aggregated accounts receivable / debt report.

    Returns:
      - debt_by_client:    {client: total_debt}
      - debt_by_warehouse: {warehouse: total_debt}
      - debt_by_month:     {YYYY-MM: total_debt}
      - status_summary:    {paid, partial, unpaid, overdue} counts
      - entries:           detailed list of each billing entry with debt info
    """
    _, role, _ = _resolve_user(x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, FINANCE_VIEW_ROLES):
        raise HTTPException(status_code=403, detail="Access denied: requires director, accounting, or admin role")

    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    debt_by_client: Dict[str, float] = {}
    debt_by_warehouse: Dict[str, float] = {}
    debt_by_month: Dict[str, float] = {}
    status_counts: Dict[str, int] = {"paid": 0, "partial": 0, "unpaid": 0, "overdue": 0}
    entries: List[Dict[str, Any]] = []

    for wh_key in BILLING_SHEETS:
        try:
            wh_entries = get_billing_entries(wh_key)
        except Exception as exc:
            logger.warning("Could not load billing for %s: %s", wh_key, exc)
            continue

        for e in wh_entries:
            period = str(e.get("period", "")).strip()
            if month and period and not (period == month or period.startswith(f"{month}-")):
                continue

            client = (e.get("client") or e.get("client_name") or "Неизвестно").strip()
            total_with_vat = _to_float(
                e.get("total_with_vat") or e.get("p1_total_with_penalties")
            )
            payment_amount = _to_float(e.get("payment_amount") or e.get("paid_amount") or 0)

            # Also check if fully paid via payment_status field
            pay_status_raw = str(e.get("payment_status", "")).strip().lower()
            if pay_status_raw in _PAID_STATUSES:
                payment_amount = total_with_vat

            debt = max(total_with_vat - payment_amount, 0.0)

            end_date = str(e.get("end_date") or e.get("project_end_date") or "")
            status = _payment_status(total_with_vat, payment_amount, end_date)

            # Accumulate
            debt_by_client[client] = debt_by_client.get(client, 0.0) + debt
            debt_by_warehouse[wh_key.upper()] = (
                debt_by_warehouse.get(wh_key.upper(), 0.0) + debt
            )
            entry_month = period[:7] if len(period) >= 7 else "unknown"
            debt_by_month[entry_month] = debt_by_month.get(entry_month, 0.0) + debt
            status_counts[status] = status_counts.get(status, 0) + 1

            entries.append({
                "warehouse": wh_key.upper(),
                "client": client,
                "period": period,
                "total_with_vat": total_with_vat,
                "payment_amount": payment_amount,
                "debt": debt,
                "payment_status": status,
            })

    return {
        "month": month,
        "debt_by_client": dict(sorted(debt_by_client.items(), key=lambda x: -x[1])),
        "debt_by_warehouse": debt_by_warehouse,
        "debt_by_month": dict(sorted(debt_by_month.items())),
        "status_summary": status_counts,
        "total_debt": sum(debt_by_client.values()),
        "entries": entries,
    }
