import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.models.deal import DealCreate, DealResponse, DealUpdate
from backend.models.common import SuccessResponse
from backend.services import deal_service
from backend.services.telegram_auth import extract_user_from_init_data
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deal", tags=["deals"])


def _get_user_id_from_header(init_data: Optional[str]) -> str:
    """Extract Telegram user ID from initData header (best-effort)."""
    if init_data:
        user = extract_user_from_init_data(init_data)
        if user:
            return str(user.get("id", ""))
    return ""


@router.post("/create", response_model=dict)
async def create_deal(
    deal: DealCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Create a new deal and write it to Google Sheets."""
    try:
        user_id = _get_user_id_from_header(x_telegram_init_data)
        deal_id = deal_service.create_deal(
            deal_data=deal.model_dump(),
            telegram_user_id=user_id,
        )
        return {"success": True, "deal_id": deal_id}
    except Exception as exc:
        logger.error("Error creating deal: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/user", response_model=list)
async def get_user_deals(
    manager: Optional[str] = None,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """Return deals, optionally filtered by manager name."""
    try:
        deals = deal_service.get_user_deals(manager_name=manager)
        return deals
    except Exception as exc:
        logger.error("Error fetching user deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{deal_id}", response_model=dict)
async def get_deal(deal_id: str) -> dict:
    """Get a single deal by ID."""
    deal = deal_service.get_deal_by_id(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.put("/{deal_id}", response_model=dict)
async def update_deal(
    deal_id: str,
    update: DealUpdate,
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Update an existing deal."""
    try:
        user_id = _get_user_id_from_header(x_telegram_init_data)
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        success = deal_service.update_deal(
            deal_id=deal_id,
            update_data=update_data,
            telegram_user_id=user_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Deal not found")
        return {"success": True, "deal_id": deal_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
