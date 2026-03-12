"""Deals router."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_current_user, require_active_user
from backend.models.schemas import Deal, DealCreate, DealUpdate, MeResponse
from backend.services.deals import (
    create_deal_service,
    get_all_deals_service,
    get_deal_service,
    get_deals_for_user,
    update_deal_service,
)

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/user", response_model=List[Dict[str, Any]])
def list_my_deals(current_user: MeResponse = Depends(get_current_user)):
    """Return deals visible to the current user (manager sees only own)."""
    require_active_user(current_user)
    deals = get_deals_for_user(current_user)
    return [d.model_dump() for d in deals]


@router.get("/all", response_model=List[Dict[str, Any]])
def list_all_deals(current_user: MeResponse = Depends(get_current_user)):
    """Return all deals (restricted to non-manager roles)."""
    require_active_user(current_user)
    from backend.config import ROLE_MANAGER
    if current_user.role == ROLE_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Менеджер не может просматривать все сделки",
        )
    deals = get_all_deals_service()
    return [d.model_dump() for d in deals]


@router.get("/{deal_id}", response_model=Dict[str, Any])
def get_deal(deal_id: str, current_user: MeResponse = Depends(get_current_user)):
    require_active_user(current_user)
    deal = get_deal_service(deal_id, current_user)
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    return deal.model_dump()


@router.post("/create", response_model=Dict[str, Any], status_code=201)
def create_deal(
    payload: DealCreate,
    current_user: MeResponse = Depends(get_current_user),
):
    require_active_user(current_user)
    from backend.config import ROLE_ACCOUNTANT
    if current_user.role == ROLE_ACCOUNTANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Бухгалтер не может создавать сделки",
        )
    deal = create_deal_service(payload.model_dump(exclude_none=True), current_user)
    return deal.model_dump()


@router.put("/{deal_id}", response_model=Dict[str, Any])
def update_deal(
    deal_id: str,
    payload: DealUpdate,
    current_user: MeResponse = Depends(get_current_user),
):
    require_active_user(current_user)
    updated = update_deal_service(deal_id, payload.model_dump(exclude_none=True), current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Сделка не найдена или доступ запрещён")
    return updated.model_dump()
