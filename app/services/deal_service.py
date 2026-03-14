"""
Deal service — high-level business logic for deals.

Wraps CRUD operations and logs actions to journal_entries.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import deals as crud_deals
from app.database.models import Deal
from app.database.schemas import DealCreate, DealUpdate
from app.services.journal_service import log_action

logger = logging.getLogger(__name__)


async def create_deal(
    db: AsyncSession,
    data: DealCreate,
    user_id: Optional[str] = None,
    role_name: Optional[str] = None,
) -> Deal:
    deal = await crud_deals.create_deal(db, data)
    await log_action(
        db,
        action="create_deal",
        user_id=user_id,
        role_name=role_name,
        entity="deal",
        entity_id=deal.id,
        details=f"deal_name={deal.deal_name}",
    )
    return deal


async def update_deal(
    db: AsyncSession,
    deal_id: int,
    data: DealUpdate,
    user_id: Optional[str] = None,
    role_name: Optional[str] = None,
) -> Optional[Deal]:
    deal = await crud_deals.update_deal(db, deal_id, data)
    if deal is not None:
        await log_action(
            db,
            action="update_deal",
            user_id=user_id,
            role_name=role_name,
            entity="deal",
            entity_id=deal_id,
            details=str(data.model_dump(exclude_none=True)),
        )
    return deal
