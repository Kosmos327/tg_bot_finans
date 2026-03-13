"""
billing.py – Billing management endpoints.

Routes
------
GET  /billing/{warehouse}                  – list all billing entries for warehouse
GET  /billing/{warehouse}/{client_name}    – get one entry
POST /billing/{warehouse}                  – create or update a billing entry
POST /billing/payment                      – mark a payment on a deal
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.models.schemas import BillingEntryCreate, BillingEntryResponse, BillingEntryCreateV2, PaymentMarkRequest
from backend.services import settings_service
from backend.services.billing_service import (
    get_billing_entries,
    get_billing_entry,
    upsert_billing_entry,
)
from backend.services.deals_service import update_deal, get_deal_by_id
from backend.services.journal_service import append_journal_entry
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    BILLING_EDIT_ROLES,
    FINANCE_VIEW_ROLES,
    check_role,
)
from backend.services.sheets_service import SheetsError
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

_ALLOWED_WAREHOUSES = {"msk", "nsk", "ekb"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_user(init_data: Optional[str], role_header: Optional[str] = None) -> tuple:
    """Return (user_id, role, full_name) from Telegram initData or X-User-Role header."""
    if init_data:
        user = extract_user_from_init_data(init_data)
        if user:
            user_id = str(user.get("id", ""))
            role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
            full_name = settings_service.get_user_full_name(user_id) if user_id else ""
            return user_id, role, full_name

    # Fall back to X-User-Role header (Mini App password auth)
    if role_header and role_header.strip():
        from backend.services.permissions import ALLOWED_ROLES
        role = role_header.strip().lower()
        if role in ALLOWED_ROLES:
            return "", role, ""

    return "", NO_ACCESS_ROLE, ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{warehouse}", response_model=List[Dict[str, Any]])
async def list_billing(
    warehouse: str,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """List all billing entries for the given warehouse (msk/nsk/ekb)."""
    if warehouse.lower() not in _ALLOWED_WAREHOUSES:
        raise HTTPException(status_code=400, detail=f"Unknown warehouse: {warehouse}")

    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    # Managers can only view billing; other roles with finance_view or billing_edit
    if not (check_role(role, BILLING_EDIT_ROLES) or check_role(role, FINANCE_VIEW_ROLES)):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return get_billing_entries(warehouse.lower())
    except (SheetsError, ValueError) as exc:
        logger.error("Error fetching billing for %s: %s", warehouse, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{warehouse}/{client_name}", response_model=Dict[str, Any])
async def get_billing(
    warehouse: str,
    client_name: str,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Get billing entry for a specific client in a warehouse."""
    if warehouse.lower() not in _ALLOWED_WAREHOUSES:
        raise HTTPException(status_code=400, detail=f"Unknown warehouse: {warehouse}")

    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not (check_role(role, BILLING_EDIT_ROLES) or check_role(role, FINANCE_VIEW_ROLES)):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        entry = get_billing_entry(warehouse.lower(), client_name)
    except (SheetsError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if entry is None:
        raise HTTPException(status_code=404, detail="Client not found in billing sheet")

    return entry


@router.post("/{warehouse}", response_model=Dict[str, Any])
async def upsert_billing(
    warehouse: str,
    body: Dict[str, Any],
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Create or update a billing entry for a client in the given warehouse.

    Accepts both old format (client_name + p1/p2 period objects) and new
    VAT-aware format (client + shipments_with_vat etc.).

    Requires the manager or admin role.
    Totals are calculated automatically.
    """
    if warehouse.lower() not in _ALLOWED_WAREHOUSES:
        raise HTTPException(status_code=400, detail=f"Unknown warehouse: {warehouse}")

    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, BILLING_EDIT_ROLES):
        raise HTTPException(status_code=403, detail="Access denied: billing edit requires manager or admin role")

    # Detect format: new format uses 'client' key or shipments_with_vat
    is_new_fmt = "client" in body or "shipments_with_vat" in body

    if is_new_fmt:
        # Validate with BillingEntryCreateV2
        try:
            parsed = BillingEntryCreateV2(**body)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        entry_dict: Dict[str, Any] = parsed.model_dump(exclude_none=True)
    else:
        # Old format: BillingEntryCreate with p1/p2 sub-objects
        try:
            parsed_old = BillingEntryCreate(**body)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        entry_dict = {"client_name": parsed_old.client_name}
        for period_prefix, period_obj in [("p1", parsed_old.p1), ("p2", parsed_old.p2)]:
            if period_obj is None:
                continue
            for field, val in period_obj.model_dump().items():
                if val is not None:
                    entry_dict[f"{period_prefix}_{field}"] = val

    try:
        result = upsert_billing_entry(
            warehouse=warehouse.lower(),
            entry_data=entry_dict,
            user=user_id or full_name or role,
            role=role,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error upserting billing %s: %s", warehouse, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/payment/mark", response_model=Dict[str, Any])
async def mark_payment(
    body: PaymentMarkRequest,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Mark a payment on a deal.

    Updates paid_amount and remaining_amount in the 'deals' sheet.
    Requires manager or admin role.
    """
    user_id, role, full_name = _resolve_user(x_telegram_init_data, x_user_role)
    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, BILLING_EDIT_ROLES):
        raise HTTPException(status_code=403, detail="Access denied")

    if body.payment_amount < 0:
        raise HTTPException(status_code=422, detail="payment_amount must be non-negative")

    try:
        # Fetch the current deal to compute updated totals
        deal = get_deal_by_id(body.deal_id)
    except SheetsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Use new-structure field names if present, else fall back
    def _f(key: str) -> float:
        val = deal.get(key, "") or "0"
        try:
            return float(str(val).replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            return 0.0

    current_paid = _f("paid_amount") or _f("paid")
    revenue = _f("revenue_with_vat") or _f("charged_with_vat") or _f("amount_with_vat")

    new_paid = current_paid + body.payment_amount
    new_remaining = max(revenue - new_paid, 0.0)

    update_data: Dict[str, Any] = {}
    # Determine which field names are in the deal dict and use them
    if "paid_amount" in deal:
        update_data["paid_amount"] = str(new_paid)
        update_data["remaining_amount"] = str(new_remaining)
    else:
        update_data["paid"] = str(new_paid)

    try:
        success = update_deal(
            deal_id=body.deal_id,
            update_data=update_data,
            telegram_user_id=user_id,
            user_role=role,
            full_name=full_name or body.user,
        )
    except SheetsError as exc:
        logger.error("Sheets error marking payment for deal %s: %s", body.deal_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not success:
        raise HTTPException(status_code=404, detail="Deal not found")

    append_journal_entry(
        telegram_user_id=user_id,
        full_name=full_name or body.user,
        user_role=role,
        action="mark_payment",
        deal_id=body.deal_id,
        payload_summary=f"payment_amount={body.payment_amount} new_paid={new_paid} remaining={new_remaining}",
    )

    return {
        "success": True,
        "deal_id": body.deal_id,
        "payment_amount": body.payment_amount,
        "paid_amount": new_paid,
        "remaining_amount": new_remaining,
    }
