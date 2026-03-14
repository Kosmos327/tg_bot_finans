"""CRUD operations for deals."""

from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Deal
from app.database.schemas import DealCreate, DealUpdate


def _apply_financials(deal: Deal) -> None:
    """Auto-calculate VAT breakdown and profit metrics."""
    if deal.amount_with_vat and deal.vat_rate:
        rate = Decimal(str(deal.vat_rate))
        amount_vat = Decimal(str(deal.amount_with_vat))
        deal.amount_without_vat = round(amount_vat / (1 + rate), 2)
        deal.vat_amount = round(amount_vat - deal.amount_without_vat, 2)

    # Remaining amount
    paid = deal.paid_amount or Decimal("0")
    if deal.amount_with_vat:
        deal.remaining_amount = max(Decimal(str(deal.amount_with_vat)) - paid, Decimal("0"))

    # Marginal income and gross profit (without_vat basis)
    if deal.amount_without_vat is not None:
        ve1 = deal.variable_expense_1 or Decimal("0")
        ve2 = deal.variable_expense_2 or Decimal("0")
        deal.marginal_income = round(
            Decimal(str(deal.amount_without_vat)) - ve1 - ve2, 2
        )
        prod = deal.production_expense or Decimal("0")
        deal.gross_profit = round(
            Decimal(str(deal.marginal_income)) - prod, 2
        )
        if deal.manager_bonus_pct:
            deal.manager_bonus_amount = round(
                Decimal(str(deal.gross_profit)) * deal.manager_bonus_pct / 100, 2
            )


async def create_deal(db: AsyncSession, data: DealCreate) -> Deal:
    deal = Deal(**data.model_dump(exclude_none=True))
    _apply_financials(deal)
    db.add(deal)
    await db.flush()
    await db.refresh(deal)
    return deal


async def get_deals(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[Deal]:
    result = await db.execute(select(Deal).offset(skip).limit(limit))
    return result.scalars().all()


async def get_deal(db: AsyncSession, deal_id: int) -> Optional[Deal]:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    return result.scalar_one_or_none()


async def update_deal(
    db: AsyncSession, deal_id: int, data: DealUpdate
) -> Optional[Deal]:
    deal = await get_deal(db, deal_id)
    if deal is None:
        return None
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(deal, key, value)
    _apply_financials(deal)
    await db.flush()
    await db.refresh(deal)
    return deal
