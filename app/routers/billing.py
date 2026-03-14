"""
Billing router — POST /billing, GET /billing.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import billing as crud
from app.database.database import get_db
from app.database.schemas import BillingCreate, BillingResponse
from app.services.billing_service import create_billing as svc_create

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("", response_model=BillingResponse, status_code=201)
async def create_billing(
    data: BillingCreate,
    db: AsyncSession = Depends(get_db),
) -> BillingResponse:
    entry = await svc_create(db, data)
    return BillingResponse.model_validate(entry)


@router.get("", response_model=List[BillingResponse])
async def list_billing(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
) -> List[BillingResponse]:
    entries = await crud.get_billing_entries(db, skip=skip, limit=limit)
    return [BillingResponse.model_validate(e) for e in entries]
