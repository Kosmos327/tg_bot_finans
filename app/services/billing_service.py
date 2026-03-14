"""
Billing service — high-level business logic for billing entries.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import billing as crud_billing
from app.database.models import BillingEntry
from app.database.schemas import BillingCreate
from app.services.journal_service import log_action

logger = logging.getLogger(__name__)


async def create_billing(
    db: AsyncSession,
    data: BillingCreate,
    user_id: Optional[str] = None,
    role_name: Optional[str] = None,
) -> BillingEntry:
    entry = await crud_billing.create_billing(db, data)
    await log_action(
        db,
        action="create_billing",
        user_id=user_id,
        role_name=role_name,
        entity="billing_entry",
        entity_id=entry.id,
        details=f"client_id={entry.client_id} warehouse_id={entry.warehouse_id}",
    )
    return entry
