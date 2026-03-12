import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.models.deal import DealCreate, DealUpdate
from backend.services import deals_service, settings_service
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    can_see_all_deals,
    filter_update_payload,
)
from backend.services.sheets_service import SheetsError
from backend.services.telegram_auth import extract_user_from_init_data
from backend.services.journal_service import append_journal_entry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deal", tags=["deals"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_user(init_data: Optional[str]) -> tuple:
    """
    Return (user_id, role, full_name) from Telegram initData.
    Falls back to ("", NO_ACCESS_ROLE, "") on failure.
    """
    if not init_data:
        return "", NO_ACCESS_ROLE, ""
    user = extract_user_from_init_data(init_data)
    if not user:
        return "", NO_ACCESS_ROLE, ""
    user_id = str(user.get("id", ""))
    role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
    full_name = settings_service.get_user_full_name(user_id) if user_id else ""
    return user_id, role, full_name


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/create", response_model=dict)
async def create_deal(
    deal: DealCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Create a new deal (requires manager role or higher)."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        deal_id = deals_service.create_deal(
            deal_data=deal.model_dump(),
            telegram_user_id=user_id,
            user_role=role,
            full_name=full_name,
        )
        return {"success": True, "deal_id": deal_id}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error creating deal: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error creating deal: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/all", response_model=list)
async def get_all_deals(
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """Return all deals (accountant / director / head_of_sales only)."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

    if not can_see_all_deals(role):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return deals_service.get_all_deals()
    except SheetsError as exc:
        logger.error("Sheets error fetching all deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/user", response_model=list)
async def get_user_deals(
    manager: Optional[str] = None,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """
    Return deals for the current user.
    Managers see only their own deals; higher roles may pass ?manager= to filter.
    """
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if role == "manager":
            # Managers always see only their own deals; ignore the ?manager param
            return deals_service.get_deals_by_user(full_name) if full_name else []
        # Higher roles can optionally filter by a specific manager name
        if manager:
            return deals_service.get_deals_by_user(manager)
        return deals_service.get_all_deals()
    except SheetsError as exc:
        logger.error("Sheets error fetching deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/filter", response_model=list)
async def get_deals_filtered(
    manager: Optional[str] = None,
    client: Optional[str] = None,
    status: Optional[str] = None,
    business_direction: Optional[str] = None,
    month: Optional[str] = None,
    paid: Optional[bool] = None,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """Filter deals by various criteria."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    filters: dict = {}
    if manager is not None:
        filters["manager"] = manager
    if client is not None:
        filters["client"] = client
    if status is not None:
        filters["status"] = status
    if business_direction is not None:
        filters["business_direction"] = business_direction
    if month is not None:
        filters["month"] = month
    if paid is not None:
        filters["paid"] = paid

    # Managers are restricted to their own name
    if role == "manager" and full_name:
        filters["manager"] = full_name

    try:
        return deals_service.get_deals_filtered(filters)
    except SheetsError as exc:
        logger.error("Sheets error filtering deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{deal_id}", response_model=dict)
async def get_deal(
    deal_id: str,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Get a single deal by ID."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        deal = deals_service.get_deal_by_id(deal_id)
    except SheetsError as exc:
        logger.error("Sheets error fetching deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Managers may only view their own deals
    if role == "manager" and deal.get("manager") != full_name:
        raise HTTPException(status_code=403, detail="Access denied")

    return deal


@router.put("/{deal_id}", response_model=dict)
async def update_deal(
    deal_id: str,
    update: DealUpdate,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Update an existing deal (role-based field permissions enforced)."""
    user_id, role, full_name = _resolve_user(x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    # Strip None values from the update payload
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    # For managers, verify the deal belongs to them before updating
    if role == "manager":
        try:
            deal = deals_service.get_deal_by_id(deal_id)
        except SheetsError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if deal is None:
            raise HTTPException(status_code=404, detail="Deal not found")
        if deal.get("manager") != full_name:
            append_journal_entry(
                telegram_user_id=user_id,
                full_name=full_name,
                user_role=role,
                action="forbidden_update_attempt",
                deal_id=deal_id,
                payload_summary="Manager attempted to update another manager's deal",
            )
            raise HTTPException(status_code=403, detail="Access denied")

    try:
        success = deals_service.update_deal(
            deal_id=deal_id,
            update_data=update_data,
            telegram_user_id=user_id,
            user_role=role,
            full_name=full_name,
        )
    except SheetsError as exc:
        logger.error("Sheets error updating deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error updating deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    if not success:
        raise HTTPException(status_code=404, detail="Deal not found")

    return {"success": True, "deal_id": deal_id}
