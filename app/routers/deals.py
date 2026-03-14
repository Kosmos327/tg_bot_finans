"""
Deals router — POST /deals, GET /deals, GET /deals/{id}.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import deals as crud
from app.database.database import get_db
from app.database.schemas import DealCreate, DealResponse, DealUpdate
from app.services.deal_service import create_deal as svc_create
from app.services.deal_service import update_deal as svc_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deals", tags=["deals"])


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    data: DealCreate,
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    deal = await svc_create(db, data)
    return DealResponse.model_validate(deal)


@router.get("", response_model=List[DealResponse])
async def list_deals(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> List[DealResponse]:
    deals = await crud.get_deals(db, skip=skip, limit=limit)
    return [DealResponse.model_validate(d) for d in deals]


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: int,
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    deal = await crud.get_deal(db, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    return DealResponse.model_validate(deal)


@router.put("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: int,
    data: DealUpdate,
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    deal = await svc_update(db, deal_id, data)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    return DealResponse.model_validate(deal)
